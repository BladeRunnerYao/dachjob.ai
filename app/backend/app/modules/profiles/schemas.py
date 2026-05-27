from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ProfileResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    full_name: str
    headline: str
    location: str | None = None
    timezone: str | None = None
    raw_cv_md: str
    profile_json: Any = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CVUploadRequest(BaseModel):
    raw_cv_md: str


class URLImportRequest(BaseModel):
    url: str
