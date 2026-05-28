from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantContext
from app.core.config import get_settings
from app.core.tenant import get_tenant_context
from app.db.models import ResumeArtifact
from app.db.session import get_db
from app.modules.background_tasks.execution import run_or_enqueue
from app.modules.resumes.schemas import GenerateResumeRequest, ResumeResponse
from app.modules.resumes.service import generate_resume
from app.modules.storage.service import StorageService

router = APIRouter(prefix="/api/jobs/{job_id}", tags=["resumes"])
artifact_router = APIRouter(prefix="/api/resumes", tags=["resumes"])


def _artifact_owner_filters(tenant: TenantContext):
    filters = [ResumeArtifact.tenant_id == tenant.id]
    if tenant.user_id is not None:
        filters.append(ResumeArtifact.user_id == tenant.user_id)
    return filters


@router.post("/resume", status_code=201)
async def create_resume(
    job_id: UUID,
    body: GenerateResumeRequest = GenerateResumeRequest(),
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    confirmed_skills = body.confirmed_skills or []
    if settings.worker_enabled:
        mode, result = await run_or_enqueue(
            db,
            tenant=tenant,
            kind="resume_generate",
            payload={
                "tenant_id": str(tenant.id),
                "tenant_slug": tenant.slug,
                "user_id": str(tenant.user_id) if tenant.user_id else None,
                "job_id": str(job_id),
                "confirmed_skills": confirmed_skills,
            },
            celery_task=__import__(
                "app.workers.tasks", fromlist=["generate_resume_task"]
            ).generate_resume_task,
            sync_runner=lambda: generate_resume(
                db, tenant, job_id, confirmed_skills=confirmed_skills
            ),
            result_serializer=lambda r: {
                "resume_artifact_id": str(r.id),
                "html_object_key": r.html_object_key,
                "pdf_object_key": r.pdf_object_key,
            },
        )
        if mode == "queued":
            return result
        artifact = result
    else:
        artifact = await generate_resume(db, tenant, job_id, confirmed_skills=confirmed_skills)
    return artifact


@router.get("/resume", response_model=ResumeResponse | None)
async def get_latest_resume(
    job_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ResumeArtifact)
        .where(ResumeArtifact.job_id == job_id, *_artifact_owner_filters(tenant))
        .order_by(ResumeArtifact.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@artifact_router.get("/{artifact_id}/html")
async def get_resume_html(
    artifact_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ResumeArtifact)
        .where(ResumeArtifact.id == artifact_id, *_artifact_owner_filters(tenant))
        .limit(1)
    )
    artifact = result.scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=404, detail="Resume artifact not found")

    storage = StorageService()
    try:
        html = storage.download(artifact.html_object_key).decode("utf-8")
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Resume HTML not found") from exc

    return HTMLResponse(html)


@artifact_router.get("/{artifact_id}/pdf")
async def get_resume_pdf(
    artifact_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ResumeArtifact)
        .where(ResumeArtifact.id == artifact_id, *_artifact_owner_filters(tenant))
        .limit(1)
    )
    artifact = result.scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=404, detail="Resume artifact not found")

    if not artifact.pdf_object_key:
        raise HTTPException(status_code=404, detail="PDF not available for this artifact")

    storage = StorageService()
    try:
        pdf_bytes = storage.download(artifact.pdf_object_key)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Resume PDF not found") from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=resume-{artifact_id}.pdf"},
    )
