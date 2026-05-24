from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantContext
from app.core.tenant import get_tenant_context
from app.db.models import ResumeArtifact
from app.db.session import get_db
from app.modules.profiles.repository import get_profile_by_tenant
from app.modules.resumes.schemas import EvidenceResponse, ResumeResponse
from app.modules.resumes.service import generate_resume, list_evidence
from app.modules.storage.service import StorageService

router = APIRouter(prefix="/api/jobs/{job_id}", tags=["resumes"])
artifact_router = APIRouter(prefix="/api/resumes", tags=["resumes"])


@router.get("/evidence", response_model=list[EvidenceResponse])
async def get_evidence(
    job_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    profile = await get_profile_by_tenant(db, tenant.id)
    if not profile:
        return []
    return await list_evidence(db, tenant.id, profile.id)


@router.post("/resume", response_model=ResumeResponse, status_code=201)
async def create_resume(
    job_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    artifact = await generate_resume(db, tenant, job_id)
    return artifact


@router.get("/resume", response_model=ResumeResponse | None)
async def get_latest_resume(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ResumeArtifact)
        .where(ResumeArtifact.job_id == job_id)
        .order_by(ResumeArtifact.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@artifact_router.get("/{artifact_id}/html", response_class=HTMLResponse)
async def get_resume_html(
    artifact_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ResumeArtifact).where(ResumeArtifact.id == artifact_id).limit(1)
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
