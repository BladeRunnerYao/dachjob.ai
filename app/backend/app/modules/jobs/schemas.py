from __future__ import annotations

from uuid import UUID
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class JobResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    title: str
    company: str
    url: str | None = None
    location: str | None = None
    source: str | None = None
    source_job_id: str | None = None
    posted_at: datetime | None = None
    employment_type: str | None = None
    workplace: str | None = None
    salary_text: str | None = None
    raw_jd: str
    parsed_json: Any = None
    scraped_json: Any = None
    skills: list["JobSkillResponse"] = Field(default_factory=list)
    status: str
    score: float | None = None
    recommendation: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JobCreateRequest(BaseModel):
    title: str
    company: str
    url: str | None = None
    location: str | None = None
    raw_jd: str


class JobImportRequest(BaseModel):
    urls: list[str]


class JobSkillResponse(BaseModel):
    id: UUID
    name: str
    category: str
    source: str
    confidence: float | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
