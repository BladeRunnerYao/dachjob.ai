import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.sql import func

from app.db.session import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = Column(Text, unique=True, nullable=False, index=True)
    name = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)
    password_hash = Column(Text, nullable=True)
    google_id = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Membership(Base):
    __tablename__ = "memberships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role = Column(Text, nullable=False)


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    full_name = Column(Text, nullable=False)
    headline = Column(Text, nullable=False)
    location = Column(Text, nullable=True)
    timezone = Column(Text, nullable=True)
    raw_cv_md = Column(Text, nullable=False)
    profile_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class EvidenceChunk(Base):
    __tablename__ = "evidence_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("candidate_profiles.id"), nullable=False)
    source_type = Column(Text, nullable=False)
    source_label = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    metadata_json = Column(JSONB, nullable=True)
    embedding = Column(ARRAY(Float), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class JobPosting(Base):
    __tablename__ = "job_postings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    title = Column(Text, nullable=False)
    company = Column(Text, nullable=False)
    url = Column(Text, nullable=True)
    location = Column(Text, nullable=True)
    source = Column(Text, nullable=True)
    source_job_id = Column(Text, nullable=True)
    posted_at = Column(DateTime(timezone=True), nullable=True)
    employment_type = Column(Text, nullable=True)
    workplace = Column(Text, nullable=True)
    salary_text = Column(Text, nullable=True)
    raw_jd = Column(Text, nullable=False)
    parsed_json = Column(JSONB, nullable=True)
    scraped_json = Column(JSONB, nullable=True)
    status = Column(Text, nullable=False, default="new")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class JobSkill(Base):
    __tablename__ = "job_skills"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("job_postings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(Text, nullable=False)
    category = Column(Text, nullable=False)
    source = Column(Text, nullable=False, default="parser")
    confidence = Column(Numeric, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("job_id", "name", "category", name="uq_job_skills_job_name_category"),
    )


class MatchReport(Base):
    __tablename__ = "match_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("job_postings.id"), nullable=False)
    overall_score = Column(Numeric, nullable=False)
    recommendation = Column(Text, nullable=False)
    breakdown_json = Column(JSONB, nullable=False)
    gaps_json = Column(JSONB, nullable=True)
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ResumeArtifact(Base):
    __tablename__ = "resume_artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("job_postings.id"), nullable=False)
    match_report_id = Column(UUID(as_uuid=True), ForeignKey("match_reports.id"), nullable=True)
    html_object_key = Column(Text, nullable=False)
    pdf_object_key = Column(Text, nullable=True)
    provenance_json = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Application(Base):
    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("job_postings.id"), nullable=False)
    resume_artifact_id = Column(
        UUID(as_uuid=True), ForeignKey("resume_artifacts.id"), nullable=True
    )
    status = Column(Text, nullable=False, default="Evaluated")
    score = Column(Numeric, nullable=True)
    notes = Column(Text, nullable=True)
    next_action_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    key_hash = Column(Text, nullable=False)
    prefix = Column(Text, nullable=False, index=True)
    name = Column(Text, nullable=False)
    created_by = Column(Text, nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LLMRun(Base):
    __tablename__ = "llm_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    task = Column(Text, nullable=False)
    provider = Column(Text, nullable=False)
    model = Column(Text, nullable=False)
    prompt_version = Column(Text, nullable=True)
    input_hash = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=False)
    tokens_json = Column(JSONB, nullable=True)
    status = Column(Text, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
