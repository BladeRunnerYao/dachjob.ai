import logging
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantContext
from app.core.config import get_settings
from app.modules.background_tasks.repository import create_task, get_task, update_task_status
from app.modules.background_tasks.schemas import BackgroundTaskResponse

logger = logging.getLogger(__name__)


async def run_or_enqueue(
    db: AsyncSession,
    *,
    tenant: TenantContext,
    kind: str,
    payload: dict,
    celery_task: Callable | None = None,
    sync_runner: Callable[[], Awaitable[Any]] | None = None,
    result_serializer: Callable[[Any], dict] | None = None,
    idempotency_key: str | None = None,
) -> tuple[str, Any]:
    settings = get_settings()

    task = await create_task(
        db,
        tenant_id=tenant.id,
        user_id=tenant.user_id,
        kind=kind,
        payload=payload,
        idempotency_key=idempotency_key,
    )

    logger.info(
        "background_task_created | task_id=%s kind=%s tenant_id=%s user_id=%s worker_enabled=%s",
        task.id, kind, tenant.id, tenant.user_id, settings.worker_enabled,
    )

    if settings.worker_enabled and celery_task is not None:
        try:
            result = celery_task.apply_async(
                args=[str(task.id)],
                kwargs={},
            )
            await update_task_status(
                db, task.id,
                status="queued",
                celery_task_id=result.id,
            )
            logger.info(
                "celery_enqueue_success | background_task_id=%s celery_task_id=%s kind=%s",
                task.id, result.id, kind,
            )
            task_response = BackgroundTaskResponse(
                id=task.id,
                kind=task.kind,
                status="queued",
                progress=0,
                result=None,
                error=None,
                created_at=task.created_at,
                started_at=task.started_at,
                finished_at=task.finished_at,
            )
            return ("queued", task_response)
        except Exception as exc:
            logger.error(
                "celery_enqueue_failed | background_task_id=%s kind=%s error=%s",
                task.id, kind, str(exc)[:200],
            )
            if not settings.worker_fallback_to_sync:
                await update_task_status(db, task.id, status="failed", error_json={
                    "message": f"Failed to enqueue task: {str(exc)[:200]}",
                })
                raise

            logger.warning(
                "celery_fallback_to_sync | background_task_id=%s kind=%s",
                task.id, kind,
            )

    if sync_runner is None:
        raise ValueError("sync_runner is required when worker is disabled or fallback is used")

    try:
        result = await sync_runner()
        serialized = result_serializer(result) if result_serializer else {"result": "ok"}
        await update_task_status(db, task.id, status="succeeded", result_json=serialized)
        logger.info(
            "sync_execution_succeeded | background_task_id=%s kind=%s",
            task.id, kind,
        )
        return ("sync", result)
    except Exception as exc:
        await update_task_status(db, task.id, status="failed", error_json={
            "message": str(exc)[:500],
            "exception_type": type(exc).__name__,
        })
        logger.error(
            "sync_execution_failed | background_task_id=%s kind=%s error=%s",
            task.id, kind, str(exc)[:200],
        )
        raise
