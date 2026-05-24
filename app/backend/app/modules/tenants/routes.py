from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantContext
from app.core.tenant import get_tenant_context
from app.db.models import Tenant
from app.db.session import get_db
from app.modules.tenants.schemas import TenantResponse

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


@router.get("", response_model=list[TenantResponse])
async def get_tenants(
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Tenant).where(Tenant.id == tenant.id).limit(1))
    current_tenant = result.scalar_one_or_none()
    return [current_tenant] if current_tenant else []
