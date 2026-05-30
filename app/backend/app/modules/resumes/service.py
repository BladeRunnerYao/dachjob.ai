import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantContext
from app.db.models import CandidateProfile, ResumeArtifact
from app.modules.jobs.repository import get_job
from app.modules.llm_gateway.gateway import LLMGateway
from app.modules.resumes.artifacts import create_resume_artifact, persist_resume_artifacts
from app.modules.resumes.prompt_builder import ResumeOutput, build_llm_prompt
from app.modules.resumes.renderer_html import render_resume_html
from app.modules.resumes.renderer_pdf import render_resume_pdf

logger = logging.getLogger(__name__)

__all__ = [
    "_build_llm_prompt",
    "_generate_html_resume",
    "_html_to_pdf",
    "_profile_query_for_resume",
    "create_resume_artifact",
    "generate_resume",
]


def _profile_query_for_resume(tenant: TenantContext):
    query = select(CandidateProfile).where(CandidateProfile.tenant_id == tenant.id)
    if tenant.user_id is not None:
        query = query.where(CandidateProfile.user_id == tenant.user_id)
    return query.limit(1)


async def generate_resume(
    db: AsyncSession,
    tenant: TenantContext,
    job_id: uuid.UUID,
    confirmed_skills: list[str] | None = None,
) -> ResumeArtifact:
    job = await get_job(db, job_id, tenant.id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    profile_result = await db.execute(_profile_query_for_resume(tenant))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise ValueError("No profile found for the authenticated user")

    parsed_job = job.parsed_json or {"title": job.title, "company": job.company, "raw": job.raw_jd}

    html: str | None = None
    provenance: dict[str, Any] = {"method": "template", "job_id": str(job_id)}

    try:
        gateway = LLMGateway()
        messages = build_llm_prompt(profile, parsed_job, confirmed_skills)
        result = await gateway.run_json(
            tenant_id=tenant.id,
            task="resume_generate",
            prompt_version="1.0",
            model_tier="quality",
            messages=messages,
            output_schema=ResumeOutput,
            thinking=False,
        )
        html = result.html
        provenance = {
            "method": "llm",
            "job_id": str(job_id),
            "provider": gateway.last_provider,
            "model": gateway.last_model,
        }
    except Exception:
        logger.exception("LLM resume generation failed, falling back to template renderer")

    if not html:
        html, prov = render_resume_html(profile, parsed_job)
        provenance = {**provenance, **prov}

    pdf_bytes = render_resume_pdf(html)
    return await persist_resume_artifacts(
        db=db,
        tenant=tenant,
        job_id=job_id,
        html=html,
        pdf_bytes=pdf_bytes,
        provenance=provenance,
    )


_build_llm_prompt = build_llm_prompt
_generate_html_resume = render_resume_html
_html_to_pdf = render_resume_pdf
