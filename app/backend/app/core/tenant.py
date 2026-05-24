from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantContext, is_public_route, validate_auth
from app.core.config import get_settings
from app.core.redis_client import cache
from app.db.models import Tenant
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)


async def get_tenant_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    if is_public_route(request.url.path, request.method):
        settings = get_settings()
        slug = settings.default_tenant_slug
        cached = await cache.get_json("tenant:slug", slug)
        if cached:
            ctx = TenantContext(
                id=_coerce_uuid(cached.get("id")),
                slug=cached["slug"],
                name=cached["name"],
            )
            return ctx
        result = await db.execute(select(Tenant).where(Tenant.slug == slug).limit(1))
        tenant = result.scalar_one_or_none()
        if tenant:
            data = {"id": str(tenant.id), "slug": tenant.slug, "name": tenant.name}
            await cache.set_json("tenant:slug", slug, data)
            await cache.set_json("tenant:id", str(tenant.id), data)
            return TenantContext(id=tenant.id, slug=tenant.slug, name=tenant.name)
        return TenantContext(slug=slug, name=slug)

    return await validate_auth(credentials, x_api_key=x_api_key, db=db)


def _coerce_uuid(value: str | None):
    if not value:
        return None
    from uuid import UUID

    try:
        return UUID(value)
    except ValueError:
        return None
