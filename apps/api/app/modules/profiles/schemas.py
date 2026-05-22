from uuid import UUID
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class EvidenceChunkResponse(BaseModel):
    id: UUID
    source_type: str
    source_label: str
    content: str
    metadata_json: Any = None
    model_config = {"from_attributes": True}


class ProfileResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    full_name: str
    headline: str
    location: str | None = None
    timezone: str | None = None
    raw_cv_md: str
    profile_json: Any = None
    evidence_chunks: list[EvidenceChunkResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CVUploadRequest(BaseModel):
    raw_cv_md: str
