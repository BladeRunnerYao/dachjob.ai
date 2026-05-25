import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BackgroundTask


async def create_task(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None,
    kind: str,
    payload: dict | None = None,
    idempotency_key: str | None = None,
) -> BackgroundTask:
    now = datetime.now(timezone.utc)
    task = BackgroundTask(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        kind=kind,
        status="queued",
        payload_json=payload or {},
        idempotency_key=idempotency_key,
        created_at=now,
        updated_at=now,
    )
    db.add(task)
    await db.flush()
    return task


async def get_task(
    db: AsyncSession, task_id: uuid.UUID, tenant_id: uuid.UUID | None = None
) -> BackgroundTask | None:
    stmt = select(BackgroundTask).where(BackgroundTask.id == task_id)
    if tenant_id is not None:
        stmt = stmt.where(BackgroundTask.tenant_id == tenant_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_tasks(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    status: str | None = None,
    kind: str | None = None,
    user_id: uuid.UUID | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[BackgroundTask], int]:
    stmt = select(BackgroundTask).where(BackgroundTask.tenant_id == tenant_id)
    count_stmt = (
        select(func.count())
        .select_from(BackgroundTask)
        .where(BackgroundTask.tenant_id == tenant_id)
    )
    if status:
        stmt = stmt.where(BackgroundTask.status == status)
        count_stmt = count_stmt.where(BackgroundTask.status == status)
    if kind:
        stmt = stmt.where(BackgroundTask.kind == kind)
        count_stmt = count_stmt.where(BackgroundTask.kind == kind)
    if user_id:
        stmt = stmt.where(BackgroundTask.user_id == user_id)
        count_stmt = count_stmt.where(BackgroundTask.user_id == user_id)

    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    result = await db.execute(
        stmt.order_by(BackgroundTask.created_at.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all()), total


async def update_task_status(
    db: AsyncSession,
    task_id: uuid.UUID,
    *,
    status: str,
    progress: int | None = None,
    result_json: dict | None = None,
    error_json: dict | None = None,
    celery_task_id: str | None = None,
) -> BackgroundTask | None:
    values: dict = {"status": status}
    if progress is not None:
        values["progress"] = progress
    if result_json is not None:
        values["result_json"] = result_json
    if error_json is not None:
        values["error_json"] = error_json
    if celery_task_id is not None:
        values["celery_task_id"] = celery_task_id
    if (
        status == "running"
        and not (
            await db.execute(select(BackgroundTask.started_at).where(BackgroundTask.id == task_id))
        ).scalar()
    ):
        values["started_at"] = datetime.now(timezone.utc)
    if status in ("succeeded", "failed", "cancelled"):
        values["finished_at"] = datetime.now(timezone.utc)

    await db.execute(update(BackgroundTask).where(BackgroundTask.id == task_id).values(**values))
    await db.flush()

    result = await db.execute(select(BackgroundTask).where(BackgroundTask.id == task_id))
    return result.scalar_one_or_none()


async def cancel_task(
    db: AsyncSession, task_id: uuid.UUID, tenant_id: uuid.UUID
) -> BackgroundTask | None:
    task = await get_task(db, task_id, tenant_id)
    if not task:
        return None
    if task.status not in ("queued", "retrying"):
        return task
    return await update_task_status(db, task_id, status="cancelled")
