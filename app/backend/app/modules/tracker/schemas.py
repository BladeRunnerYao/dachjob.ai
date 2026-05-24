from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

VALID_STATUSES = [
    "Evaluated",
    "Applied",
    "Responded",
    "Interview",
    "Offer",
    "Rejected",
    "Discarded",
    "SKIP",
]


class ApplicationResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    job_id: UUID
    job_title: str | None = None
    company: str | None = None
    resume_artifact_id: UUID | None = None
    status: str
    score: Decimal | None = None
    recommendation: str | None = None
    notes: str | None = None
    next_action_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class ApplicationCreate(BaseModel):
    job_id: UUID
    status: str = "Evaluated"
    notes: str | None = None


class ApplicationUpdate(BaseModel):
    status: str | None = None
    score: Decimal | None = None
    notes: str | None = None
    next_action_at: datetime | None = None


class AutofillPayload(BaseModel):
    first_name: str
    last_name: str
    email: str = "demo@dachjob.ai"
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    work_authorization: str = ""
    current_employer: str = ""
    years_of_experience: int = 0
    resume_link: str = ""
    cover_note: str = ""
    screening_answers: list[dict] = []
