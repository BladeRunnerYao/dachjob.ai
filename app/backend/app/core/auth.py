import hashlib
import secrets
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Header
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.redis_client import cache
from app.core.security import decode_access_token, pwd_context
from app.db.models import ApiKey, Membership, Tenant, User


class TenantContext(BaseModel):
    id: UUID | None = None
    slug: str
    name: str = ""

    model_config = {"arbitrary_types_allowed": True}


API_KEY_PREFIX = "dach_"

PUBLIC_ROUTES = {
    ("GET", "/api/health"),
    ("GET", "/api/version"),
    ("POST", "/api/auth/register"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/forgot-password"),
    ("POST", "/api/auth/reset-password"),
    ("POST", "/api/auth/google"),
}


def generate_api_key() -> str:
    raw = secrets.token_hex(16)
    return f"{API_KEY_PREFIX}{raw}"


def hash_api_key(raw: str) -> str:
    return pwd_context.hash(raw)


def verify_api_key(raw: str, hashed: str) -> bool:
    return pwd_context.verify(raw, hashed)


def _extract_prefix(raw: str) -> str:
    return raw[: len(API_KEY_PREFIX) + 8]


def _unauthorized(message: str = "Valid Bearer token or X-API-Key header is required") -> AppError:
    return AppError("authentication_required", message, status_code=401)


def _coerce_uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


def _is_resume_public_route(path: str, method: str) -> bool:
    if method.upper() != "GET":
        return False
    parts = path.strip("/").split("/")
    return (
        len(parts) == 4
        and parts[0] == "api"
        and parts[1] == "resumes"
        and parts[3] in ("html", "pdf")
        and _coerce_uuid(parts[2]) is not None
    )


def is_public_route(path: str, method: str = "GET") -> bool:
    normalized_method = method.upper()
    if normalized_method == "OPTIONS":
        return True
    if (normalized_method, path) in PUBLIC_ROUTES:
        return True
    return False


def is_rate_limit_exempt_route(path: str, method: str = "GET") -> bool:
    return method.upper() == "OPTIONS" or path in {"/api/health", "/api/version"}


async def validate_bearer_token(
    credentials: HTTPAuthorizationCredentials | None,
    db: AsyncSession,
    tenant_slug: str | None = None,
) -> tuple[User, Tenant]:
    if not credentials:
        raise _unauthorized("Bearer token is required")

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise _unauthorized("Invalid or expired Bearer token")

    user_id = _coerce_uuid(payload.get("sub"))
    token_tenant_id = _coerce_uuid(payload.get("tenant_id"))
    if not user_id:
        raise _unauthorized("Bearer token is missing a valid user id")
    if not token_tenant_id and not tenant_slug:
        raise _unauthorized("Bearer token is missing a valid tenant id")

    token_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()[:32]
    cached = await cache.get_json("auth:jwt", token_hash)
    if cached:
        tenant_id = _coerce_uuid(cached.get("tenant_id"))
        stmt = select(User).where(User.id == user_id).limit(1)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if user:
            return user, Tenant(id=tenant_id, slug=cached["slug"], name=cached["name"])

    stmt = (
        select(User, Tenant)
        .join(Membership, Membership.user_id == User.id)
        .join(Tenant, Tenant.id == Membership.tenant_id)
        .where(User.id == user_id)
    )
    if tenant_slug:
        stmt = stmt.where(Tenant.slug == tenant_slug)
    else:
        stmt = stmt.where(Tenant.id == token_tenant_id)

    result = await db.execute(stmt.limit(1))
    row = result.one_or_none()
    if not row:
        raise _unauthorized("User is not a member of the requested tenant")

    user, tenant = row
    await cache.set_json(
        "auth:jwt",
        token_hash,
        {"tenant_id": str(tenant.id), "slug": tenant.slug, "name": tenant.name},
    )
    return user, tenant


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


async def validate_api_key(raw_key: str, db: AsyncSession) -> TenantContext:
    if not raw_key.startswith(API_KEY_PREFIX):
        raise _unauthorized()

    now = datetime.now(timezone.utc)
    prefix = _extract_prefix(raw_key)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()[:16]

    cached = await cache.get_json("auth:apikey", prefix, key_hash)
    if cached:
        return TenantContext(
            id=_coerce_uuid(cached.get("id")),
            slug=cached["slug"],
            name=cached["name"],
        )

    result = await db.execute(
        select(ApiKey).where(
            ApiKey.prefix == prefix,
            ApiKey.is_active.is_(True),
        )
    )
    keys = result.scalars().all()

    for key in keys:
        if not verify_api_key(raw_key, key.key_hash):
            continue
        if key.expires_at and _normalize_datetime(key.expires_at) <= now:
            continue

        result = await db.execute(select(Tenant).where(Tenant.id == key.tenant_id).limit(1))
        tenant = result.scalar_one_or_none()
        if not tenant:
            continue

        key.last_used_at = now
        await db.flush()

        await cache.set_json(
            "auth:apikey",
            prefix,
            key_hash,
            {"id": str(tenant.id), "slug": tenant.slug, "name": tenant.name},
        )
        return TenantContext(id=tenant.id, slug=tenant.slug, name=tenant.name)

    raise _unauthorized()


async def validate_auth(
    credentials: HTTPAuthorizationCredentials | None,
    x_api_key: str | None = Header(None),
    db: AsyncSession | None = None,
) -> TenantContext:
    if db is None:
        raise RuntimeError("Database session is required for authentication")

    if credentials:
        _user, tenant = await validate_bearer_token(credentials, db)
        return TenantContext(id=tenant.id, slug=tenant.slug, name=tenant.name)

    if x_api_key:
        return await validate_api_key(x_api_key, db)

    raise _unauthorized()
