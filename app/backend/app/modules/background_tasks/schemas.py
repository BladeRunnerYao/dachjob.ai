from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class BackgroundTaskResponse(BaseModel):
    id: UUID
    kind: str
    status: str
    progress: int = 0
    result: Any = None
    error: Any = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = {"from_attributes": True}


class BackgroundTaskListResponse(BaseModel):
    items: list[BackgroundTaskResponse]
    total: int


class BackgroundTaskCancelResponse(BaseModel):
    id: UUID
    status: str
