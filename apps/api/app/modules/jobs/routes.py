from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.modules.jobs.schemas import JobResponse, JobCreateRequest
from app.modules.jobs.repository import list_jobs_by_tenant, get_job, create_job

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    if tenant.id is None:
        return []
    return await list_jobs_by_tenant(db, tenant.id)


@router.post("", response_model=JobResponse, status_code=201)
async def create_job_endpoint(
    body: JobCreateRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    return await create_job(
        db, tenant.id, body.title, body.company, body.raw_jd, body.url, body.location
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_endpoint(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    return await get_job(db, job_id)
