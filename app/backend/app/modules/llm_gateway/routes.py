from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantContext
from app.core.tenant import get_tenant_context
from app.db.models import LLMRun
from app.db.session import get_db
from app.modules.llm_gateway.schemas import PaginatedLLMRunsResponse

router = APIRouter(prefix="/api/llm-runs", tags=["llm-gateway"])


@router.get("", response_model=PaginatedLLMRunsResponse)
async def list_llm_runs(
    task: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    base = select(LLMRun).where(LLMRun.tenant_id == tenant.id)

    if task:
        base = base.where(LLMRun.task == task)
    if status:
        base = base.where(LLMRun.status == status)

    count_stmt = select(func.count()).select_from(base.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = base.order_by(LLMRun.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    items = list(result.scalars().all())

    return PaginatedLLMRunsResponse(items=items, total=total)
