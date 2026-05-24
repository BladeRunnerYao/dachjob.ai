from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.modules.jobs.importer import import_job_urls
from app.modules.jobs.repository import create_job, get_job, list_jobs_by_tenant
from app.modules.jobs.schemas import (
    ImportError,
    JobCreateRequest,
    JobImportRequest,
    JobImportResponse,
    JobResponse,
)

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


@router.post("/import", response_model=JobImportResponse, status_code=201)
async def import_jobs_endpoint(
    body: JobImportRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    if tenant.id is None:
        raise AppError("tenant_not_found", "Tenant context is required")
    urls = [url.strip() for url in body.urls if url.strip()]
    if not urls:
        raise AppError("job_urls_required", "Provide at least one job URL")
    if len(urls) > 10:
        raise AppError("too_many_job_urls", "Import at most 10 job URLs at a time")
    imported, errors = await import_job_urls(db, tenant, urls)
    return JobImportResponse(
        imported=imported,
        errors=[ImportError(url=e["url"], error=e["error"]) for e in errors],
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_endpoint(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    return await get_job(db, job_id)
