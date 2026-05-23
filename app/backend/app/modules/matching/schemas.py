from uuid import UUID
from datetime import datetime
from pydantic import BaseModel


class ParseResponse(BaseModel):
    job_id: UUID
    status: str
    parsed_json: dict | None = None


class MatchResponse(BaseModel):
    id: UUID
    job_id: UUID
    overall_score: float
    recommendation: str
    breakdown_json: dict
    gaps_json: dict | None = None
    explanation: str | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


class ScoreBreakdown(BaseModel):
    role_relevance: float = 0.0
    skill_match: float = 0.0
    evidence_strength: float = 0.0
    dach_feasibility: float = 0.0
    compensation_fit: float = 0.0
    growth_story_value: float = 0.0


class FitExplanation(BaseModel):
    overall_score: float
    recommendation: str
    breakdown: dict[str, float]
    top_reasons: list[str]
    gaps: list[str]
    explanation: str
