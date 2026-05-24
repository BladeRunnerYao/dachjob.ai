import secrets
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Header, Request
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import decode_access_token, pwd_context
from app.db.models import ApiKey, Tenant


class TenantContext(BaseModel):
    id: UUID | None = None
    slug: str
    name: str = ""

    model_config = {"arbitrary_types_allowed": True}


API_KEY_PREFIX = "dach_"

PUBLIC_ROUTES = {
    "/api/health",
    "/api/version",
    "/api/auth/register",
    "/api/auth/login",
    "/api/auth/google",
}

PUBLIC_ROUTE_PREFIXES = ("/api/resumes/",)


def generate_api_key() -> str:
    raw = secrets.token_hex(16)
    return f"{API_KEY_PREFIX}{raw}"


def hash_api_key(raw: str) -> str:
    return pwd_context.hash(raw)


def verify_api_key(raw: str, hashed: str) -> bool:
    return pwd_context.verify(raw, hashed)


def _extract_prefix(raw: str) -> str:
    return raw[: len(API_KEY_PREFIX) + 8]


def is_public_route(path: str) -> bool:
    if path in PUBLIC_ROUTES:
        return True
    for prefix in PUBLIC_ROUTE_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


async def validate_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
    x_api_key: str | None = Header(None),
    db: AsyncSession | None = None,
) -> TenantContext:
    if credentials:
        payload = decode_access_token(credentials.credentials)
        if payload and payload.get("tenant_id"):
            tenant_id = UUID(payload["tenant_id"])
            result = await db.execute(
                select(Tenant).where(Tenant.id == tenant_id).limit(1)
            )
            tenant = result.scalar_one_or_none()
            if tenant:
                return TenantContext(id=tenant.id, slug=tenant.slug, name=tenant.name)

        if payload and payload.get("sub"):
            result = await db.execute(
                select(Tenant).where(Tenant.slug == "default").limit(1)
            )
            tenant = result.scalar_one_or_none()
            if tenant:
                return TenantContext(id=tenant.id, slug=tenant.slug, name=tenant.name)

    if x_api_key:
        prefix = _extract_prefix(x_api_key)
        keys = (
            await db.execute(
                select(ApiKey).where(
                    ApiKey.prefix == prefix,
                    ApiKey.is_active == 1,
                )
            )
        ).scalars().all()

        for key in keys:
            if verify_api_key(x_api_key, key.key_hash):
                if key.expires_at and key.expires_at < datetime.now(timezone.utc):
                    continue
                key.last_used_at = datetime.now(timezone.utc)
                await db.flush()

                result = await db.execute(
                    select(Tenant).where(Tenant.id == key.tenant_id).limit(1)
                )
                tenant = result.scalar_one_or_none()
                if tenant:
                    return TenantContext(id=tenant.id, slug=tenant.slug, name=tenant.name)

    raise AppError(
        "authentication_required",
        "Valid Bearer token or X-API-Key header is required",
        status_code=401,
    )
