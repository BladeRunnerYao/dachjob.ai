import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantContext
from app.db.models import MatchReport, ResumeArtifact
from app.modules.storage.service import StorageService


async def create_resume_artifact(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    html_object_key: str,
    provenance: dict[str, Any] | None = None,
    user_id: uuid.UUID | None = None,
) -> ResumeArtifact:
    artifact = ResumeArtifact(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        job_id=job_id,
        html_object_key=html_object_key,
        provenance_json=provenance or {},
    )
    db.add(artifact)
    await db.flush()
    return artifact


def build_resume_object_keys(job_id: uuid.UUID, file_id: uuid.UUID) -> tuple[str, str]:
    return f"resumes/{job_id}/{file_id}.html", f"resumes/{job_id}/{file_id}.pdf"


async def persist_resume_artifacts(
    db: AsyncSession,
    tenant: TenantContext,
    job_id: uuid.UUID,
    html: str,
    pdf_bytes: bytes,
    provenance: dict[str, Any],
    storage: StorageService | None = None,
) -> ResumeArtifact:
    storage = storage or StorageService()
    file_id = uuid.uuid4()
    html_object_key, pdf_object_key = build_resume_object_keys(job_id, file_id)

    storage.upload(html_object_key, html.encode("utf-8"), content_type="text/html; charset=utf-8")
    storage.upload(pdf_object_key, pdf_bytes, content_type="application/pdf")

    match_result = await db.execute(
        select(MatchReport)
        .where(
            MatchReport.job_id == job_id,
            MatchReport.tenant_id == tenant.id,
        )
        .order_by(MatchReport.created_at.desc())
        .limit(1)
    )
    match_report = match_result.scalar_one_or_none()

    artifact = ResumeArtifact(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=tenant.user_id,
        job_id=job_id,
        match_report_id=match_report.id if match_report else None,
        html_object_key=html_object_key,
        pdf_object_key=pdf_object_key,
        provenance_json=provenance,
    )
    db.add(artifact)
    await db.flush()
    return artifact
