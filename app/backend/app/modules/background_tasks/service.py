import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.models import BackgroundTask
from app.modules.background_tasks.repository import create_task

logger = logging.getLogger(__name__)


async def create_background_task(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None,
    kind: str,
    payload: dict | None = None,
) -> BackgroundTask:
    task = await create_task(
        db, tenant_id=tenant_id, user_id=user_id, kind=kind, payload=payload
    )
    logger.info(
        "background_task_created | task_id=%s kind=%s tenant_id=%s user_id=%s",
        task.id, kind, tenant_id, user_id,
    )
    return task


def validate_worker_available() -> None:
    settings = get_settings()
    if not settings.worker_enabled:
        return
    try:
        from app.workers.celery_app import celery_app
        celery_app.control.ping(timeout=settings.worker_enqueue_timeout_seconds)
    except Exception as exc:
        if settings.worker_fallback_to_sync:
            logger.warning(
                "worker_unavailable_fallback_to_sync | error=%s",
                str(exc)[:200],
            )
        else:
            raise AppError(
                "worker_unavailable",
                "Background worker is not available. Try again later.",
                status_code=503,
            ) from exc
