import logging
from uuid import UUID

import httpx

from app.core.auth import TenantContext
from app.core.redis_client import cache
from app.db.session import async_session_factory
from app.modules.background_tasks.repository import get_task, update_task_status
from app.modules.jobs.importer import import_job_urls
from app.modules.jobs.repository import get_job
from app.modules.matching.service import compute_match, parse_job_posting
from app.modules.resumes.service import generate_resume
from app.workers.celery_app import celery_app, run_async

logger = logging.getLogger(__name__)


async def _load_task(db, background_task_id: str):
    task_id = UUID(background_task_id)
    task = await get_task(db, task_id, None)
    if task is None:
        raise ValueError(f"BackgroundTask {background_task_id} not found")
    return task


async def _run_inner(background_task_id: str, async_fn, *, result_serializer=None):
    async with async_session_factory() as db:
        try:
            task = await _load_task(db, background_task_id)
            if task.status == "cancelled":
                logger.info("task_skipped_cancelled | background_task_id=%s", background_task_id)
                return
            await update_task_status(db, task.id, status="running")

            result = await async_fn(db, task)
            serialized = result_serializer(result) if result_serializer else {"result": "ok"}
            await update_task_status(db, task.id, status="succeeded", result_json=serialized)
            await db.commit()
            logger.info(
                "task_succeeded | background_task_id=%s kind=%s",
                background_task_id,
                task.kind,
            )
        except Exception as exc:
            logger.exception(
                "task_failed | background_task_id=%s kind=%s error=%s",
                background_task_id,
                task.kind,
                str(exc)[:200],
            )
            try:
                await db.rollback()
                await update_task_status(
                    db,
                    task.id,
                    status="failed",
                    error_json={
                        "message": str(exc)[:500],
                        "exception_type": type(exc).__name__,
                    },
                )
                await db.commit()
            except Exception:
                try:
                    await db.rollback()
                except Exception:
                    pass


@celery_app.task(
    bind=True,
    autoretry_for=(httpx.HTTPError,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=3,
)
def import_jobs_task(self, background_task_id: str):
    async def _run(db, task):
        payload = task.payload_json or {}
        tenant = TenantContext(
            id=UUID(payload["tenant_id"]),
            slug=payload.get("tenant_slug", ""),
            user_id=UUID(payload["user_id"]) if payload.get("user_id") else None,
        )
        urls = payload.get("urls", [])
        imported, errors = await import_job_urls(db, tenant, urls)
        await cache.delete("jobs:list", str(tenant.id))
        return {
            "imported_job_ids": [str(j.id) for j in imported],
            "errors": [{"url": e["url"], "error": e["error"]} for e in errors],
        }

    run_async(_run_inner(background_task_id, _run, result_serializer=lambda r: r))


@celery_app.task(
    bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=2
)
def parse_job_task(self, background_task_id: str):
    async def _run(db, task):
        payload = task.payload_json or {}
        tenant = TenantContext(
            id=UUID(payload["tenant_id"]),
            slug=payload.get("tenant_slug", ""),
            user_id=UUID(payload["user_id"]) if payload.get("user_id") else None,
        )
        job = await get_job(db, UUID(payload["job_id"]), tenant.id)
        if not job:
            raise ValueError(f"Job {payload['job_id']} not found")
        result = await parse_job_posting(db, tenant, job, force=True)
        await cache.delete("jobs:list", str(tenant.id))
        return {"job_id": payload["job_id"], "status": result["status"]}

    run_async(_run_inner(background_task_id, _run, result_serializer=lambda r: r))


@celery_app.task(
    bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=2
)
def compute_match_task(self, background_task_id: str):
    async def _run(db, task):
        payload = task.payload_json or {}
        tenant = TenantContext(
            id=UUID(payload["tenant_id"]),
            slug=payload.get("tenant_slug", ""),
            user_id=UUID(payload["user_id"]) if payload.get("user_id") else None,
        )
        report = await compute_match(db, tenant, UUID(payload["job_id"]))
        await cache.delete("jobs:list", str(tenant.id))
        return {
            "job_id": payload["job_id"],
            "match_report_id": str(report.id),
            "overall_score": float(report.overall_score),
            "recommendation": report.recommendation,
        }

    run_async(_run_inner(background_task_id, _run, result_serializer=lambda r: r))


@celery_app.task(
    bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=2
)
def generate_resume_task(self, background_task_id: str):
    async def _run(db, task):
        payload = task.payload_json or {}
        tenant = TenantContext(
            id=UUID(payload["tenant_id"]),
            slug=payload.get("tenant_slug", ""),
            user_id=UUID(payload["user_id"]) if payload.get("user_id") else None,
        )
        artifact = await generate_resume(db, tenant, UUID(payload["job_id"]))
        return {
            "job_id": payload["job_id"],
            "resume_artifact_id": str(artifact.id),
            "html_object_key": artifact.html_object_key,
            "pdf_object_key": artifact.pdf_object_key,
        }

    run_async(_run_inner(background_task_id, _run, result_serializer=lambda r: r))


@celery_app.task(
    bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=3
)
def send_email_task(self, background_task_id: str):
    async def _run(db, task):
        from app.core.email import send_reset_email

        payload = task.payload_json or {}
        to_email = payload.get("to_email", "")
        reset_link = payload.get("reset_link", "")
        result = send_reset_email(to_email, reset_link)
        return {"to_email": to_email, "delivered": result}

    run_async(_run_inner(background_task_id, _run, result_serializer=lambda r: r))
