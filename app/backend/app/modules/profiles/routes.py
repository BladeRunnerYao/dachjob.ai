from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantContext, get_tenant_context
from app.db.session import get_db
from app.modules.profiles.schemas import ProfileResponse, CVUploadRequest, URLImportRequest
from app.modules.profiles.repository import (
    get_profile_by_tenant,
    upsert_profile,
    create_evidence_chunks,
    delete_evidence_by_profile,
    list_evidence_by_profile,
)
from app.modules.profiles.extractor import fetch_url_content, extract_pdf_text, convert_to_cv_markdown
from app.modules.resumes.service import chunk_cv_md

router = APIRouter(prefix="/api/profile", tags=["profiles"])


async def _profile_response(db: AsyncSession, profile):
    chunks = await list_evidence_by_profile(db, profile.id)
    return {
        "id": profile.id,
        "tenant_id": profile.tenant_id,
        "full_name": profile.full_name,
        "headline": profile.headline,
        "location": profile.location,
        "timezone": profile.timezone,
        "raw_cv_md": profile.raw_cv_md,
        "profile_json": profile.profile_json,
        "evidence_chunks": chunks,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


@router.get("", response_model=ProfileResponse | None)
async def get_profile(
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    if tenant.id is None:
        return None
    profile = await get_profile_by_tenant(db, tenant.id)
    if not profile:
        return None
    return await _profile_response(db, profile)


@router.post("/import-url", response_model=ProfileResponse)
async def import_profile_from_url(
    body: URLImportRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    if tenant.id is None:
        raise HTTPException(status_code=400, detail="Tenant required")

    raw_text = await fetch_url_content(body.url)
    cv_md = await convert_to_cv_markdown(raw_text, body.url, tenant.id)

    profile = await upsert_profile(
        db, tenant.id, "Unknown", "Unknown", cv_md
    )
    profile.profile_json = {"source_url": body.url}

    await delete_evidence_by_profile(db, profile.id)
    chunks = chunk_cv_md(cv_md, profile.id, tenant.id)
    if chunks:
        await create_evidence_chunks(db, tenant.id, profile.id, chunks)

    return await _profile_response(db, profile)


@router.post("/import-pdf", response_model=ProfileResponse)
async def import_profile_from_pdf(
    file: UploadFile = File(...),
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    if tenant.id is None:
        raise HTTPException(status_code=400, detail="Tenant required")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    pdf_bytes = await file.read()
    raw_text = extract_pdf_text(pdf_bytes)
    cv_md = await convert_to_cv_markdown(raw_text, file.filename, tenant.id)

    profile = await upsert_profile(
        db, tenant.id, "Unknown", "Unknown", cv_md
    )
    profile.profile_json = {"source_pdf": file.filename}

    await delete_evidence_by_profile(db, profile.id)
    chunks = chunk_cv_md(cv_md, profile.id, tenant.id)
    if chunks:
        await create_evidence_chunks(db, tenant.id, profile.id, chunks)

    return await _profile_response(db, profile)


@router.post("/cv", response_model=ProfileResponse)
async def upload_cv(
    body: CVUploadRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    profile = await upsert_profile(
        db, tenant.id, "Demo User", "Senior AI Platform Engineer", body.raw_cv_md
    )

    await delete_evidence_by_profile(db, profile.id)
    chunks = chunk_cv_md(body.raw_cv_md, profile.id, tenant.id)
    if chunks:
        await create_evidence_chunks(db, tenant.id, profile.id, chunks)

    return await _profile_response(db, profile)
