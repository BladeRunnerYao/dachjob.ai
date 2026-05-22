from uuid import UUID

from fastapi import Header
from pydantic import BaseModel

from app.core.config import get_settings


class TenantContext(BaseModel):
    id: UUID | None = None
    slug: str
    name: str = ""


async def get_tenant_context(
    x_tenant_slug: str | None = Header(None),
) -> TenantContext:
    slug = x_tenant_slug or get_settings().default_tenant_slug
    return TenantContext(slug=slug)
