from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import JobPosting, MatchReport


async def _attach_latest_match(db: AsyncSession, jobs: list[JobPosting]) -> list[JobPosting]:
    for job in jobs:
        result = await db.execute(
            select(MatchReport)
            .where(MatchReport.job_id == job.id)
            .order_by(MatchReport.created_at.desc())
            .limit(1)
        )
        report = result.scalar_one_or_none()
        job.score = float(report.overall_score) if report else None
        job.recommendation = report.recommendation if report else None
    return jobs


async def list_jobs_by_tenant(
    db: AsyncSession, tenant_id: UUID
) -> list[JobPosting]:
    result = await db.execute(
        select(JobPosting)
        .where(JobPosting.tenant_id == tenant_id)
        .order_by(JobPosting.created_at.desc())
    )
    return await _attach_latest_match(db, list(result.scalars().all()))


async def get_job(db: AsyncSession, job_id: UUID) -> JobPosting | None:
    result = await db.execute(
        select(JobPosting).where(JobPosting.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        return None
    return (await _attach_latest_match(db, [job]))[0]


async def create_job(
    db: AsyncSession,
    tenant_id: UUID,
    title: str,
    company: str,
    raw_jd: str,
    url: str | None = None,
    location: str | None = None,
) -> JobPosting:
    job = JobPosting(
        tenant_id=tenant_id,
        title=title,
        company=company,
        raw_jd=raw_jd,
        url=url,
        location=location,
    )
    db.add(job)
    await db.flush()
    return job
