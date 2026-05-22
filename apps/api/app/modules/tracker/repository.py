from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Application, JobPosting
from app.modules.tracker.schemas import VALID_STATUSES


async def list_applications(
    db: AsyncSession, tenant_id: UUID
) -> list[Application]:
    result = await db.execute(
        select(Application, JobPosting.title, JobPosting.company)
        .join(JobPosting, Application.job_id == JobPosting.id, isouter=True)
        .where(Application.tenant_id == tenant_id)
        .order_by(Application.created_at.desc())
    )
    rows = result.all()
    applications = []
    for app, job_title, company in rows:
        app.job_title = job_title
        app.company = company
        applications.append(app)
    return applications


async def get_application(
    db: AsyncSession, application_id: UUID
) -> Application | None:
    result = await db.execute(
        select(Application, JobPosting.title, JobPosting.company)
        .join(JobPosting, Application.job_id == JobPosting.id, isouter=True)
        .where(Application.id == application_id)
    )
    row = result.one_or_none()
    if row is None:
        return None
    app, job_title, company = row
    app.job_title = job_title
    app.company = company
    return app


async def create_application(
    db: AsyncSession, tenant_id: UUID, job_id: UUID, status: str = "Evaluated", notes: str | None = None
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
    await db.flush()
    return app


async def update_application(
    db: AsyncSession, application_id: UUID, updates: dict
) -> Application | None:
    result = await db.execute(
        select(Application).where(Application.id == application_id)
    )
    app = result.scalar_one_or_none()
    if not app:
        return None
    if "status" in updates and updates["status"] is not None:
        if updates["status"] not in VALID_STATUSES:
            raise ValueError(f"Invalid status: {updates['status']}. Must be one of {VALID_STATUSES}")
    for key, value in updates.items():
        if value is not None:
            setattr(app, key, value)
    await db.flush()
    return app
