from uuid import UUID
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class JobResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    title: str
    company: str
    url: str | None = None
    location: str | None = None
    raw_jd: str
    parsed_json: Any = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobCreateRequest(BaseModel):
    title: str
    company: str
    url: str | None = None
    location: str | None = None
    raw_jd: str
