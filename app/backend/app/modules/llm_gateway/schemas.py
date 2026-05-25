from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class ParsedJobPosting(BaseModel):
    title: str
    company: str
    location: str | None = None
    work_model: str | None = None
    language_requirements: list[str] = []
    must_have_skills: list[str] = []
    nice_to_have_skills: list[str] = []
    salary_range: str | None = None
    seniority: str | None = None
    dach_signals: dict[str, str] = {}


class FitExplanation(BaseModel):
    overall_score: float
    recommendation: str
    breakdown: dict[str, float]
    top_reasons: list[str]
    gaps: list[str]
    explanation: str


class EvidenceSelection(BaseModel):
    chunk_ids: list[str]
    relevance_scores: dict[str, float]
    selected_for_requirements: dict[str, list[str]]


class GeneratedResume(BaseModel):
    html_content: str
    provenance: list[dict]


class ScreeningAnswerSet(BaseModel):
    answers: list[dict[str, str]]


class LLMRunResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    task: str
    provider: str
    model: str
    prompt_version: str | None = None
    latency_ms: int
    tokens_json: Any = None
    status: str
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedLLMRunsResponse(BaseModel):
    items: list[LLMRunResponse]
    total: int
