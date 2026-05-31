from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Application, JobPosting
from app.modules.tracker.schemas import VALID_STATUSES

ACTIVE_APPLICATION_STATUSES = {"Applied", "Interview", "Rejected", "Offer"}
JOB_STATUS_BY_APPLICATION_STATUS = {
    "Applied": "applied",
    "Interview": "interview",
    "Rejected": "rejected",
    "Offer": "offer",
}


async def list_applications(db: AsyncSession, tenant_id: UUID) -> list[Application]:
    result = await db.execute(
        select(Application, JobPosting.title, JobPosting.company)
        .join(JobPosting, Application.job_id == JobPosting.id, isouter=True)
        .where(
            Application.tenant_id == tenant_id, Application.status.in_(ACTIVE_APPLICATION_STATUSES)
        )
        .order_by(Application.updated_at.desc(), Application.created_at.desc())
    )
    rows = result.all()
    applications = []
    for app, job_title, company in rows:
        app.job_title = job_title
        app.company = company
        applications.append(app)
    return applications


async def get_application(
    db: AsyncSession, application_id: UUID, tenant_id: UUID | None = None
) -> Application | None:
    stmt = (
        select(Application, JobPosting.title, JobPosting.company)
        .join(JobPosting, Application.job_id == JobPosting.id, isouter=True)
        .where(Application.id == application_id)
    )
    if tenant_id is not None:
        stmt = stmt.where(Application.tenant_id == tenant_id)
    result = await db.execute(stmt)
    row = result.one_or_none()
    if row is None:
        return None
    app, job_title, company = row
    app.job_title = job_title
    app.company = company
    return app


async def create_application(
    db: AsyncSession,
    tenant_id: UUID,
    job_id: UUID,
    status: str = "Evaluated",
    notes: str | None = None,
) -> Application:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}. Must be one of {VALID_STATUSES}")
    app = Application(
        tenant_id=tenant_id,
        job_id=job_id,
        status=status,
        notes=notes,
    )
    db.add(app)
    await _sync_job_application_status(db, tenant_id, job_id, status)
    await db.flush()
    return app


async def update_application(
    db: AsyncSession, application_id: UUID, updates: dict, tenant_id: UUID | None = None
) -> Application | None:
    stmt = select(Application).where(Application.id == application_id)
    if tenant_id is not None:
        stmt = stmt.where(Application.tenant_id == tenant_id)
    result = await db.execute(stmt)
    app = result.scalar_one_or_none()
    if not app:
        return None
    if "status" in updates and updates["status"] is not None:
        if updates["status"] not in VALID_STATUSES:
            raise ValueError(
                f"Invalid status: {updates['status']}. Must be one of {VALID_STATUSES}"
            )
    for key, value in updates.items():
        if value is not None:
            setattr(app, key, value)
    if "status" in updates and updates["status"] is not None:
        await _sync_job_application_status(db, app.tenant_id, app.job_id, updates["status"])
    await db.flush()
    return app


async def _sync_job_application_status(
    db: AsyncSession,
    tenant_id: UUID,
    job_id: UUID,
    application_status: str,
) -> None:
    result = await db.execute(
        select(JobPosting).where(JobPosting.id == job_id, JobPosting.tenant_id == tenant_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        return
    job.application_status = JOB_STATUS_BY_APPLICATION_STATUS.get(application_status)
