from uuid import UUID

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.models import Tenant, User
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_tenant_slug: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> tuple[User, Tenant]:
    token = credentials.credentials if credentials else None

    if token:
        payload = decode_access_token(token)
        if payload is None:
            raise AppError("invalid_token", "Invalid or expired token")

        user_id = payload.get("sub")
        if not user_id:
            raise AppError("invalid_token", "Token missing user_id")

        result = await db.execute(select(User).where(User.id == UUID(user_id)).limit(1))
        user = result.scalar_one_or_none()
        if not user:
            raise AppError("user_not_found", "User not found")

        slug = x_tenant_slug
        if not slug and payload.get("tenant_id"):
            result = await db.execute(
                select(Tenant).where(Tenant.id == UUID(payload["tenant_id"])).limit(1)
            )
            tenant = result.scalar_one_or_none()
            if tenant:
                slug = tenant.slug

        if not slug:
            slug = "default"

        result = await db.execute(select(Tenant).where(Tenant.slug == slug).limit(1))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise AppError("tenant_not_found", "Tenant not found")

        return user, tenant

    if x_tenant_slug:
        slug = x_tenant_slug
    else:
        from app.core.config import get_settings

        slug = get_settings().default_tenant_slug

    result = await db.execute(select(Tenant).where(Tenant.slug == slug).limit(1))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise AppError("tenant_not_found", "Tenant not found")

    return None, tenant
