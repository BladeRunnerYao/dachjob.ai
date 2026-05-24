from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantContext, is_public_route, validate_auth
from app.core.config import get_settings
from app.db.models import Tenant
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)


async def get_tenant_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_api_key: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    if is_public_route(request.url.path):
        settings = get_settings()
        slug = settings.default_tenant_slug
        result = await db.execute(select(Tenant).where(Tenant.slug == slug).limit(1))
        tenant = result.scalar_one_or_none()
        if tenant:
            return TenantContext(id=tenant.id, slug=tenant.slug, name=tenant.name)
        return TenantContext(slug=slug, name=slug)

    return await validate_auth(request, credentials, x_api_key=x_api_key, db=db)
