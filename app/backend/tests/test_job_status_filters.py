import uuid

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.db.models import JobPosting
from app.modules.jobs.repository import (
    APPLICATION_JOB_STATUSES,
    VALID_JOB_STATUSES,
    _job_filters,
)


def _compiled(filters):
    return select(JobPosting).where(*filters).compile(dialect=postgresql.dialect())


def _where_clause(sql: str) -> str:
    return sql.split("WHERE", 1)[1]


def test_job_filters_include_status_when_requested():
    compiled = _compiled(_job_filters(uuid.uuid4(), status="applied"))
    where = _where_clause(str(compiled))

    assert "job_postings.tenant_id" in where
    assert "job_postings.application_status" in where
    assert set(compiled.params["application_status_1"]) == APPLICATION_JOB_STATUSES
    assert compiled.params["title_1"] == "%smoke test%"


def test_job_filters_include_saved_label_when_requested():
    where = _where_clause(str(_compiled(_job_filters(uuid.uuid4(), status="saved"))))

    assert "job_postings.tenant_id" in where
    assert "job_postings.saved" in where
    assert "job_postings.application_status" not in where


def test_job_filters_include_specific_application_stage_when_requested():
    compiled = _compiled(_job_filters(uuid.uuid4(), status="interview"))
    where = _where_clause(str(compiled))

    assert "job_postings.application_status" in where
    assert compiled.params["application_status_1"] == "interview"


def test_job_filters_omit_status_for_all_jobs():
    where = _where_clause(str(_compiled(_job_filters(uuid.uuid4()))))

    assert "job_postings.tenant_id" in where
    assert "job_postings.application_status" not in where
    assert "job_postings.saved" not in where


def test_job_status_set_matches_public_api_contract():
    assert VALID_JOB_STATUSES == {"new", "applied", "interview", "rejected", "offer"}
