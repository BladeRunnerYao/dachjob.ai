from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.modules.jobs.repository import get_job
from app.modules.matching.schemas import ParseResponse, MatchResponse
from app.modules.matching.service import parse_job_posting, compute_match

router = APIRouter(prefix="/api/jobs/{job_id}", tags=["matching"])


@router.post("/parse", response_model=ParseResponse)
async def parse_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    job = await get_job(db, job_id)
    if not job:
        raise AppError("job_not_found", "Job posting not found")
    result = await parse_job_posting(db, tenant, job)
    return ParseResponse(
        job_id=job.id, status=result["status"], parsed_json=result.get("parsed_json")
    )


@router.post("/match", response_model=MatchResponse)
async def match_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    report = await compute_match(db, tenant, job_id)
    return report
