from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.modules.profiles.repository import get_profile_by_tenant
from app.modules.resumes.schemas import EvidenceResponse, ResumeResponse
from app.modules.resumes.service import list_evidence, generate_resume

router = APIRouter(prefix="/api/jobs/{job_id}", tags=["resumes"])


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
