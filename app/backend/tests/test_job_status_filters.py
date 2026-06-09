import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.db.models import JobPosting
from app.modules.jobs import repository as jobs_repository
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


@pytest.mark.asyncio
async def test_update_job_status_refreshes_job_before_serialization(monkeypatch):
    tenant_id = uuid.uuid4()
    job = JobPosting(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        title="Backend Engineer",
        company="Example GmbH",
        raw_jd="Build APIs",
        status="new",
        saved=False,
    )

    class Result:
        def scalar_one_or_none(self):
            return job

    async def passthrough(_db, jobs):
        return jobs

    async def noop_sync(_db, _job):
        return None

    db = AsyncMock()
    db.execute.return_value = Result()
    monkeypatch.setattr(jobs_repository, "_attach_latest_match", passthrough)
    monkeypatch.setattr(jobs_repository, "_attach_skills", passthrough)
    monkeypatch.setattr(jobs_repository, "_sync_application_for_job_status", noop_sync)

    updated = await jobs_repository.update_job_status(db, job.id, tenant_id, status="applied")

    assert updated is job
    assert job.application_status == "applied"
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(job)


@pytest.mark.asyncio
async def test_delete_job_removes_related_rows_before_job(monkeypatch):
    tenant_id = uuid.uuid4()
    job_id = uuid.uuid4()
    job = JobPosting(
        id=job_id,
        tenant_id=tenant_id,
        title="Backend Engineer",
        company="Example GmbH",
        raw_jd="Build APIs",
        status="new",
    )

    async def fake_get_job(_db, requested_job_id, requested_tenant_id):
        assert requested_job_id == job_id
        assert requested_tenant_id == tenant_id
        return job

    db = AsyncMock()
    monkeypatch.setattr(jobs_repository, "get_job", fake_get_job)

    deleted = await jobs_repository.delete_job(db, job_id, tenant_id)

    assert deleted is True
    assert db.execute.await_count == 5
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_job_returns_false_for_missing_job(monkeypatch):
    async def fake_get_job(_db, _job_id, _tenant_id):
        return None

    db = AsyncMock()
    monkeypatch.setattr(jobs_repository, "get_job", fake_get_job)

    deleted = await jobs_repository.delete_job(db, uuid.uuid4(), uuid.uuid4())

    assert deleted is False
    db.execute.assert_not_awaited()
    db.flush.assert_not_awaited()
