from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantContext
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.redis_client import cache
from app.core.tenant import get_tenant_context
from app.db.models import MatchReport
from app.db.session import get_db
from app.modules.background_tasks.execution import run_or_enqueue
from app.modules.background_tasks.schemas import BackgroundTaskResponse
from app.modules.jobs.repository import get_job
from app.modules.matching.schemas import MatchResponse, ParseResponse
from app.modules.matching.service import compute_match, parse_job_posting

router = APIRouter(prefix="/api/jobs/{job_id}", tags=["matching"])


@router.post("/parse", status_code=201)
async def parse_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    job = await get_job(db, job_id, tenant.id)
    if not job:
        raise AppError("job_not_found", "Job posting not found", status_code=404)

    settings = get_settings()
    if settings.worker_enabled:
        mode, result = await run_or_enqueue(
            db,
            tenant=tenant,
            kind="job_parse",
            payload={
                "tenant_id": str(tenant.id),
                "tenant_slug": tenant.slug,
                "user_id": str(tenant.user_id) if tenant.user_id else None,
                "job_id": str(job_id),
            },
            celery_task=__import__("app.workers.tasks", fromlist=["parse_job_task"]).parse_job_task,
            sync_runner=lambda: parse_job_posting(db, tenant, job, force=True),
            result_serializer=lambda r: r,
        )
        if mode == "queued":
            await cache.delete("jobs:list", str(tenant.id))
            return BackgroundTaskResponse(**result.model_dump())
        result = result
    else:
        result = await parse_job_posting(db, tenant, job, force=True)

    await cache.delete("jobs:list", str(tenant.id))
    return ParseResponse(
        job_id=job.id, status=result["status"], parsed_json=result.get("parsed_json")
    )


@router.post("/match", status_code=201)
async def match_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    settings = get_settings()
    if settings.worker_enabled:
        mode, result = await run_or_enqueue(
            db,
            tenant=tenant,
            kind="job_match",
            payload={
                "tenant_id": str(tenant.id),
                "tenant_slug": tenant.slug,
                "user_id": str(tenant.user_id) if tenant.user_id else None,
                "job_id": str(job_id),
            },
            celery_task=__import__(
                "app.workers.tasks", fromlist=["compute_match_task"]
            ).compute_match_task,
            sync_runner=lambda: compute_match(db, tenant, job_id),
            result_serializer=lambda r: {
                "match_report_id": str(r.id),
                "overall_score": float(r.overall_score),
            },
        )
        if mode == "queued":
            await cache.delete("jobs:list", str(tenant.id))
            return BackgroundTaskResponse(**result.model_dump())
        report = result
    else:
        report = await compute_match(db, tenant, job_id)

    await cache.delete("jobs:list", str(tenant.id))
    return report


@router.get("/match", response_model=MatchResponse | None)
async def get_latest_match(
    job_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MatchReport)
        .where(MatchReport.job_id == job_id, MatchReport.tenant_id == tenant.id)
        .order_by(MatchReport.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
