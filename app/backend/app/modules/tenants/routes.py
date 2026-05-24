from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.tenants.repository import list_tenants
from app.modules.tenants.schemas import TenantResponse

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


@router.get("", response_model=list[TenantResponse])
async def get_tenants(db: AsyncSession = Depends(get_db)):
    return await list_tenants(db)
