from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import JobPosting


async def list_jobs_by_tenant(
    db: AsyncSession, tenant_id: UUID
) -> list[JobPosting]:
    result = await db.execute(
        select(JobPosting)
        .where(JobPosting.tenant_id == tenant_id)
        .order_by(JobPosting.created_at.desc())
    )
    return list(result.scalars().all())


async def get_job(db: AsyncSession, job_id: UUID) -> JobPosting | None:
    result = await db.execute(
        select(JobPosting).where(JobPosting.id == job_id)
    )
    return result.scalar_one_or_none()


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
