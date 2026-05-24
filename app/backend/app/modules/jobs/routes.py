from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantContext
from app.core.errors import AppError
from app.core.redis_client import cache
from app.core.tenant import get_tenant_context
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


async def _invalidate_jobs_cache(tenant_id):
    await cache.delete("jobs:list", str(tenant_id))


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    if tenant.id is None:
        return []
    cached = await cache.get_json("jobs:list", str(tenant.id))
    if cached is not None:
        return [JobResponse.model_validate(item) for item in cached]
    jobs = await list_jobs_by_tenant(db, tenant.id)
    serialized = [JobResponse.model_validate(job).model_dump(mode="json") for job in jobs]
    await cache.set_json("jobs:list", str(tenant.id), value=serialized)
    return jobs


@router.post("", response_model=JobResponse, status_code=201)
async def create_job_endpoint(
    body: JobCreateRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    job = await create_job(
        db, tenant.id, body.title, body.company, body.raw_jd, body.url, body.location
    )
    await _invalidate_jobs_cache(tenant.id)
    return job


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
    await _invalidate_jobs_cache(tenant.id)
    return JobImportResponse(
        imported=imported,
        errors=[ImportError(url=e["url"], error=e["error"]) for e in errors],
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_endpoint(
    job_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    job = await get_job(db, job_id, tenant.id)
    if not job:
        raise AppError("job_not_found", "Job posting not found", status_code=404)
    return job
