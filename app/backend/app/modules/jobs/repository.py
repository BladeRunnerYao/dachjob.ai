from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Application, JobPosting, JobSkill, MatchReport, ResumeArtifact
from app.modules.jobs.location_country import infer_countries_from_location, serialize_countries

APPLICATION_JOB_STATUSES = {"applied", "interview", "rejected", "offer"}
VALID_JOB_STATUSES = {"new", *APPLICATION_JOB_STATUSES}
VALID_JOB_FILTERS = {None, "saved", *VALID_JOB_STATUSES}

TRACKER_STATUS_BY_JOB_STATUS = {
    "applied": "Applied",
    "interview": "Interview",
    "rejected": "Rejected",
    "offer": "Offer",
}


def _job_filters(
    tenant_id: UUID,
    status: str | None = None,
    exclude_smoke_test: bool = True,
    company: str | None = None,
    added_date: str | None = None,
    country: str | None = None,
):
    filters = [JobPosting.tenant_id == tenant_id]
    if status == "saved":
        filters.append(JobPosting.saved.is_(True))
    elif status == "applied":
        filters.append(JobPosting.application_status.in_(APPLICATION_JOB_STATUSES))
    elif status in APPLICATION_JOB_STATUSES:
        filters.append(JobPosting.application_status == status)
    elif status == "new":
        filters.append(JobPosting.application_status.is_(None))
    if company:
        filters.append(JobPosting.company == company)
    if added_date:
        filters.append(func.date(JobPosting.created_at) == added_date)
    if country:
        filters.append(JobPosting.countries.contains(f"|{country}|"))
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
    company: str | None = None,
    added_date: str | None = None,
    country: str | None = None,
    exclude_smoke_test: bool = True,
) -> int:
    stmt = (
        select(func.count())
        .select_from(JobPosting)
        .where(
            *_job_filters(
                tenant_id,
                status=status,
                exclude_smoke_test=exclude_smoke_test,
                company=company,
                added_date=added_date,
                country=country,
            )
        )
    )
    result = await db.execute(stmt)
    return result.scalar() or 0


async def list_jobs_by_tenant(
    db: AsyncSession,
    tenant_id: UUID,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    company: str | None = None,
    added_date: str | None = None,
    country: str | None = None,
    exclude_smoke_test: bool = True,
) -> list[JobPosting]:
    stmt = (
        select(JobPosting)
        .where(
            *_job_filters(
                tenant_id,
                status=status,
                exclude_smoke_test=exclude_smoke_test,
                company=company,
                added_date=added_date,
                country=country,
            )
        )
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


async def _get_latest_application_for_job(
    db: AsyncSession, job_id: UUID, tenant_id: UUID
) -> Application | None:
    result = await db.execute(
        select(Application)
        .where(Application.job_id == job_id, Application.tenant_id == tenant_id)
        .order_by(Application.updated_at.desc(), Application.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _sync_application_for_job_status(db: AsyncSession, job: JobPosting) -> None:
    app = await _get_latest_application_for_job(db, job.id, job.tenant_id)
    tracker_status = TRACKER_STATUS_BY_JOB_STATUS.get(job.application_status)
    if tracker_status is None:
        if app and app.status in TRACKER_STATUS_BY_JOB_STATUS.values():
            app.status = "Discarded"
        return
    if app:
        app.status = tracker_status
        return
    db.add(
        Application(
            tenant_id=job.tenant_id,
            job_id=job.id,
            status=tracker_status,
            score=getattr(job, "score", None),
        )
    )


async def update_job_status(
    db: AsyncSession,
    job_id: UUID,
    tenant_id: UUID,
    status: str | None = None,
    saved: bool | None = None,
) -> JobPosting | None:
    stmt = select(JobPosting).where(JobPosting.id == job_id, JobPosting.tenant_id == tenant_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if not job:
        return None
    if saved is not None:
        job.saved = saved
    if status == "saved":
        job.saved = True
    elif status is not None:
        job.application_status = None if status == "new" else status
        await _sync_application_for_job_status(db, job)
    await db.flush()
    await db.refresh(job)
    await _attach_latest_match(db, [job])
    await _attach_skills(db, [job])
    return job


async def delete_job(db: AsyncSession, job_id: UUID, tenant_id: UUID) -> bool:
    job = await get_job(db, job_id, tenant_id)
    if not job:
        return False

    await db.execute(delete(Application).where(Application.job_id == job_id))
    await db.execute(delete(ResumeArtifact).where(ResumeArtifact.job_id == job_id))
    await db.execute(delete(MatchReport).where(MatchReport.job_id == job_id))
    await db.execute(delete(JobSkill).where(JobSkill.job_id == job_id))
    await db.execute(
        delete(JobPosting).where(JobPosting.id == job_id, JobPosting.tenant_id == tenant_id)
    )
    await db.flush()
    return True


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
    countries: list[str] | None = None,
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
        countries=serialize_countries(countries or infer_countries_from_location(location)),
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
