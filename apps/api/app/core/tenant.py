from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Tenant
from app.db.session import get_db


class TenantContext(BaseModel):
    id: UUID | None = None
    slug: str
    name: str = ""


async def get_tenant_context(
    x_tenant_slug: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> TenantContext:
    slug = x_tenant_slug or get_settings().default_tenant_slug
    result = await db.execute(select(Tenant).where(Tenant.slug == slug).limit(1))
    tenant = result.scalar_one_or_none()

    if tenant:
        return TenantContext(id=tenant.id, slug=tenant.slug, name=tenant.name)

    tenant = Tenant(slug=slug, name=slug)
    db.add(tenant)
    await db.flush()
    return TenantContext(id=tenant.id, slug=tenant.slug, name=tenant.name)
