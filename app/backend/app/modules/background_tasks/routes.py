from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantContext
from app.core.errors import AppError
from app.core.tenant import get_tenant_context
from app.db.session import get_db
from app.modules.background_tasks.repository import cancel_task, get_task, list_tasks
from app.modules.background_tasks.schemas import (
    BackgroundTaskCancelResponse,
    BackgroundTaskListResponse,
    BackgroundTaskResponse,
)

router = APIRouter(prefix="/api/tasks", tags=["background_tasks"])


def _to_response(task) -> BackgroundTaskResponse:
    return BackgroundTaskResponse(
        id=task.id,
        kind=task.kind,
        status=task.status,
        progress=task.progress,
        result=task.result_json,
        error=task.error_json,
        created_at=task.created_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
    )


@router.get("", response_model=BackgroundTaskListResponse)
async def list_background_tasks(
    status: str | None = Query(None),
    kind: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    if tenant.id is None:
        raise AppError("tenant_not_found", "Tenant context is required", status_code=401)
    items, total = await list_tasks(
        db,
        tenant.id,
        status=status,
        kind=kind,
        user_id=tenant.user_id,
        limit=limit,
        offset=offset,
    )
    return BackgroundTaskListResponse(
        items=[_to_response(t) for t in items],
        total=total,
    )


@router.get("/{task_id}", response_model=BackgroundTaskResponse)
async def get_background_task(
    task_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    if tenant.id is None:
        raise AppError("tenant_not_found", "Tenant context is required", status_code=401)
    task = await get_task(db, task_id, tenant.id)
    if not task:
        raise AppError("task_not_found", "Background task not found", status_code=404)
    return _to_response(task)


@router.post("/{task_id}/cancel", response_model=BackgroundTaskCancelResponse)
async def cancel_background_task(
    task_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    if tenant.id is None:
        raise AppError("tenant_not_found", "Tenant context is required", status_code=401)
    task = await cancel_task(db, task_id, tenant.id)
    if not task:
        raise AppError("task_not_found", "Background task not found", status_code=404)
    return BackgroundTaskCancelResponse(id=task.id, status=task.status)
