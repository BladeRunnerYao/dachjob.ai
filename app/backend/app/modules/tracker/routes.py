from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantContext
from app.core.tenant import get_tenant_context
from app.db.models import MatchReport, ResumeArtifact
from app.db.session import get_db
from app.modules.profiles.repository import get_profile_by_tenant
from app.modules.tracker.autofill import generate_autofill_payload
from app.modules.tracker.repository import (
    create_application,
    get_application,
    list_applications,
    update_application,
)
from app.modules.tracker.schemas import (
    VALID_STATUSES,
    ApplicationCreate,
    ApplicationResponse,
    ApplicationUpdate,
    AutofillPayload,
)

router = APIRouter(prefix="/api/applications", tags=["tracker"])


@router.get("", response_model=list[ApplicationResponse])
async def get_applications(
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    if tenant.id is None:
        return []
    return await list_applications(db, tenant.id)


@router.post("", response_model=ApplicationResponse, status_code=201)
async def create_application_endpoint(
    body: ApplicationCreate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    if body.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status: {body.status}. Must be one of {VALID_STATUSES}",
        )
    return await create_application(db, tenant.id, body.job_id, body.status, body.notes)


@router.get("/autofill/{application_id}", response_model=AutofillPayload)
async def autofill_endpoint(
    application_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    app = await get_application(db, application_id, tenant.id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    profile = None
    if tenant.id:
        profile = await get_profile_by_tenant(db, tenant.id)

    match_report = None
    if app.job_id:
        result = await db.execute(
            select(MatchReport)
            .where(MatchReport.job_id == app.job_id, MatchReport.tenant_id == tenant.id)
            .order_by(MatchReport.created_at.desc())
            .limit(1)
        )
        match_report = result.scalar_one_or_none()

    resume_link = None
    if app.resume_artifact_id:
        result = await db.execute(
            select(ResumeArtifact).where(
                ResumeArtifact.id == app.resume_artifact_id,
                ResumeArtifact.tenant_id == tenant.id,
            )
        )
        artifact = result.scalar_one_or_none()
        if artifact:
            resume_link = artifact.pdf_object_key or artifact.html_object_key

    return generate_autofill_payload(
        profile=profile,
        job=None,
        match_report=match_report,
        resume_link=resume_link,
    )


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application_endpoint(
    application_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    app = await get_application(db, application_id, tenant.id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


@router.patch("/{application_id}", response_model=ApplicationResponse)
async def update_application_endpoint(
    application_id: UUID,
    body: ApplicationUpdate,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    if body.status is not None and body.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status: {body.status}. Must be one of {VALID_STATUSES}",
        )
    result = await update_application(
        db, application_id, body.model_dump(exclude_unset=True), tenant.id
    )
    if not result:
        raise HTTPException(status_code=404, detail="Application not found")
    return result
