from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantContext
from app.core.errors import AppError
from app.core.redis_client import cache
from app.core.tenant import get_tenant_context
from app.db.session import get_db
from app.modules.background_tasks.execution import run_or_enqueue
from app.modules.background_tasks.schemas import BackgroundTaskResponse
from app.modules.jobs.importer import import_job_urls
from app.modules.jobs.repository import (
    VALID_JOB_STATUSES,
    count_jobs_by_tenant,
    create_job,
    get_job,
    list_jobs_by_tenant,
    update_job_status,
)
from app.modules.jobs.schemas import (
    ImportError,
    JobCreateRequest,
    JobImportRequest,
    JobImportResponse,
    JobResponse,
    JobStatusUpdateRequest,
    PaginatedJobResponse,
)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


async def _invalidate_jobs_cache(tenant_id: UUID, job_id: UUID | None = None):
    await cache.delete_pattern(f"jobs:list:{tenant_id}")
    if job_id:
        await cache.delete("job:detail", str(job_id))


@router.get("", response_model=PaginatedJobResponse)
async def list_jobs(
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(15, ge=1, le=200, description="Number of jobs per page"),
    offset: int = Query(0, ge=0, description="Number of jobs to skip"),
    status: str | None = Query(None, pattern=r"^(new|saved|applied)$"),
):
    if tenant.id is None:
        return PaginatedJobResponse(items=[], total=0, limit=limit, offset=offset)
    status_key = status or "all"
    cached = await cache.get_json("jobs:list", str(tenant.id), status_key, str(limit), str(offset))
    if cached is not None:
        return PaginatedJobResponse.model_validate(cached)
    total = await count_jobs_by_tenant(db, tenant.id, status=status)
    jobs = await list_jobs_by_tenant(db, tenant.id, limit=limit, offset=offset, status=status)
    serialized = PaginatedJobResponse(
        items=[JobResponse.model_validate(job).model_dump(mode="json") for job in jobs],
        total=total,
        limit=limit,
        offset=offset,
    )
    await cache.set_json(
        "jobs:list",
        str(tenant.id),
        status_key,
        str(limit),
        str(offset),
        value=serialized.model_dump(mode="json"),
    )
    return serialized


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


@router.post("/import", status_code=201)
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

    mode, result = await run_or_enqueue(
        db,
        tenant=tenant,
        kind="jobs_import",
        payload={
            "tenant_id": str(tenant.id),
            "tenant_slug": tenant.slug,
            "user_id": str(tenant.user_id) if tenant.user_id else None,
            "urls": urls,
        },
        celery_task=__import__("app.workers.tasks", fromlist=["import_jobs_task"]).import_jobs_task,
        sync_runner=lambda: import_job_urls(db, tenant, urls),
        result_serializer=lambda r: {
            "imported_job_ids": [str(j.id) for j in r[0]],
            "errors": [{"url": e["url"], "error": e["error"]} for e in r[1]],
        },
    )
    await _invalidate_jobs_cache(tenant.id)
    if mode == "queued":
        return BackgroundTaskResponse(**result.model_dump())

    imported, errors = result
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
    if tenant.id is not None:
        cached = await cache.get_json("job:detail", str(job_id))
        if cached is not None:
            return JobResponse.model_validate(cached)
    job = await get_job(db, job_id, tenant.id)
    if not job:
        raise AppError("job_not_found", "Job posting not found", status_code=404)
    if tenant.id is not None:
        serialized = JobResponse.model_validate(job).model_dump(mode="json")
        await cache.set_json("job:detail", str(job_id), value=serialized)
    return job


@router.patch("/{job_id}/status", response_model=JobResponse)
async def update_job_status_endpoint(
    job_id: UUID,
    body: JobStatusUpdateRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    if tenant.id is None:
        raise AppError("tenant_not_found", "Tenant context is required")
    if body.status not in VALID_JOB_STATUSES:
        raise AppError(
            "invalid_job_status", "Status must be one of new, saved, applied", status_code=422
        )
    job = await update_job_status(db, job_id, tenant.id, body.status)
    if not job:
        raise AppError("job_not_found", "Job posting not found", status_code=404)
    await _invalidate_jobs_cache(tenant.id, job_id)
    return job
