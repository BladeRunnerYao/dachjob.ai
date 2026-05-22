from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import LLMRun
from app.modules.llm_gateway.schemas import LLMRunResponse
from app.modules.llm_gateway.gateway import LLMGateway, get_gateway

router = APIRouter(prefix="/api/llm-runs", tags=["llm-gateway"])


@router.get("", response_model=list[LLMRunResponse])
async def list_llm_runs(
    task: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(LLMRun).order_by(LLMRun.created_at.desc()).limit(limit)

    if task:
        stmt = stmt.where(LLMRun.task == task)
    if status:
        stmt = stmt.where(LLMRun.status == status)

    result = await db.execute(stmt)
    return list(result.scalars().all())
