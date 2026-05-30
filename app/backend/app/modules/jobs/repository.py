from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import JobPosting, JobSkill, MatchReport

VALID_JOB_STATUSES = {"new", "saved", "applied"}


def _job_filters(
    tenant_id: UUID,
    status: str | None = None,
    exclude_smoke_test: bool = True,
):
    filters = [JobPosting.tenant_id == tenant_id]
    if status:
        filters.append(JobPosting.status == status)
    if exclude_smoke_test:
        filters.append(~JobPosting.title.ilike("%smoke test%"))
    return filters


async def _attach_latest_match(db: AsyncSession, jobs: list[JobPosting]) -> list[JobPosting]:
    if not jobs:
        return jobs
    job_ids = [job.id for job in jobs]
    result = await db.execute(
        select(MatchReport)
        .where(MatchReport.job_id.in_(job_ids))
        .order_by(MatchReport.job_id, MatchReport.created_at.desc())
    )
    reports = result.scalars().all()
    latest: dict[UUID, MatchReport] = {}
    seen: set[UUID] = set()
    for report in reports:
        if report.job_id not in seen:
            seen.add(report.job_id)
            latest[report.job_id] = report
    for job in jobs:
        report = latest.get(job.id)
        job.score = float(report.overall_score) if report else None
        job.recommendation = report.recommendation if report else None
    return jobs


async def _attach_skills(db: AsyncSession, jobs: list[JobPosting]) -> list[JobPosting]:
    if not jobs:
        return jobs
    job_ids = [job.id for job in jobs]
    result = await db.execute(
        select(JobSkill)
        .where(JobSkill.job_id.in_(job_ids))
        .order_by(JobSkill.category, JobSkill.name)
    )
    by_job: dict[UUID, list[JobSkill]] = {job.id: [] for job in jobs}
    for skill in result.scalars().all():
        by_job.setdefault(skill.job_id, []).append(skill)
    for job in jobs:
        job.skills = by_job.get(job.id, [])
    return jobs


async def count_jobs_by_tenant(
    db: AsyncSession,
    tenant_id: UUID,
    status: str | None = None,
    exclude_smoke_test: bool = True,
) -> int:
    stmt = (
        select(func.count())
        .select_from(JobPosting)
        .where(*_job_filters(tenant_id, status, exclude_smoke_test))
    )
    result = await db.execute(stmt)
    return result.scalar() or 0


async def list_jobs_by_tenant(
    db: AsyncSession,
    tenant_id: UUID,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    exclude_smoke_test: bool = True,
) -> list[JobPosting]:
    stmt = (
        select(JobPosting)
        .where(*_job_filters(tenant_id, status, exclude_smoke_test))
        .order_by(JobPosting.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    jobs = list(result.scalars().all())
    await _attach_latest_match(db, jobs)
    await _attach_skills(db, jobs)
    return jobs


async def get_job(
    db: AsyncSession, job_id: UUID, tenant_id: UUID | None = None
) -> JobPosting | None:
    stmt = select(JobPosting).where(JobPosting.id == job_id)
    if tenant_id is not None:
        stmt = stmt.where(JobPosting.tenant_id == tenant_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if not job:
        return None
    await _attach_latest_match(db, [job])
    await _attach_skills(db, [job])
    return job


async def update_job_status(
    db: AsyncSession, job_id: UUID, tenant_id: UUID, status: str
) -> JobPosting | None:
    stmt = select(JobPosting).where(JobPosting.id == job_id, JobPosting.tenant_id == tenant_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if not job:
        return None
    job.status = status
    await db.flush()
    await _attach_latest_match(db, [job])
    await _attach_skills(db, [job])
    return job


def extract_skill_items(parsed_json: dict | None) -> list[tuple[str, str]]:
    if not parsed_json:
        return []
    has_structured_skills = isinstance(parsed_json.get("must_have_skills"), list) or isinstance(
        parsed_json.get("nice_to_have_skills"), list
    )
    fields = (
        [("must_have_skills", "must_have"), ("nice_to_have_skills", "nice_to_have")]
        if has_structured_skills
        else [("skills", "must_have")]
    )
    seen: set[tuple[str, str]] = set()
    items: list[tuple[str, str]] = []
    for key, category in fields:
        values = parsed_json.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            name = str(value).strip()
            if not name:
                continue
            dedupe_key = (name.casefold(), category)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            items.append((name, category))
    return items


async def sync_job_skills(
    db: AsyncSession,
    job: JobPosting,
    parsed_json: dict | None,
    source: str = "parser",
) -> list[JobSkill]:
    await db.execute(delete(JobSkill).where(JobSkill.job_id == job.id))
    skills = [
        JobSkill(
            tenant_id=job.tenant_id,
            job_id=job.id,
            name=name,
            category=category,
            source=source,
        )
        for name, category in extract_skill_items(parsed_json)
    ]
    if skills:
        db.add_all(skills)
    await db.flush()
    job.skills = skills
    return skills


async def create_job(
    db: AsyncSession,
    tenant_id: UUID,
    title: str,
    company: str,
    raw_jd: str,
    url: str | None = None,
    location: str | None = None,
    parsed_json: dict | None = None,
    source: str | None = None,
    source_job_id: str | None = None,
    posted_at=None,
    employment_type: str | None = None,
    workplace: str | None = None,
    salary_text: str | None = None,
    scraped_json: dict | None = None,
) -> JobPosting:
    job = JobPosting(
        tenant_id=tenant_id,
        title=title,
        company=company,
        raw_jd=raw_jd,
        url=url,
        location=location,
        parsed_json=parsed_json,
        source=source,
        source_job_id=source_job_id,
        posted_at=posted_at,
        employment_type=employment_type,
        workplace=workplace,
        salary_text=salary_text,
        scraped_json=scraped_json,
        status="parsed" if parsed_json else "new",
    )
    db.add(job)
    await db.flush()
    if parsed_json:
        await sync_job_skills(db, job, parsed_json)
    return job
