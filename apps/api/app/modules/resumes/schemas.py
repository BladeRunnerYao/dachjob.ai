from uuid import UUID
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class EvidenceResponse(BaseModel):
    id: UUID
    source_type: str
    source_label: str
    content: str
    metadata_json: Any = None

    model_config = {"from_attributes": True}


class ResumeResponse(BaseModel):
    id: UUID
    job_id: UUID
    match_report_id: UUID | None = None
    html_object_key: str
    pdf_object_key: str | None = None
    provenance_json: Any
    created_at: datetime

    model_config = {"from_attributes": True}


class GenerateResumeRequest(BaseModel):
    pass
