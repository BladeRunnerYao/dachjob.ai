import re
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantContext
from app.core.redis_client import cache
from app.core.tenant import get_tenant_context
from app.db.session import get_db
from app.modules.profiles.extractor import (
    convert_to_cv_markdown,
    extract_pdf_text,
    fetch_url_content,
)
from app.modules.profiles.repository import (
    create_evidence_chunks,
    delete_evidence_by_profile,
    get_profile_by_user,
    list_evidence_by_profile,
    upsert_profile,
)
from app.modules.profiles.schemas import CVUploadRequest, ProfileResponse, URLImportRequest
from app.modules.resumes.service import chunk_cv_md

router = APIRouter(prefix="/api/profile", tags=["profiles"])


def _parse_name_and_headline(md: str) -> tuple[str | None, str | None]:
    name = None
    headline = None
    match = re.search(r"^#\s+(.+)$", md, re.MULTILINE)
    if match:
        name = match.group(1).strip()
    section_match = re.search(
        r"^##\s+Profile(?:\s*/\s*Summary)?\s*\n+(.+?)(?:\n+##\s|\Z)", md, re.MULTILINE | re.DOTALL
    )
    if section_match:
        first_sentence = section_match.group(1).strip().split(".")[0].strip()
        if first_sentence:
            headline = first_sentence[:200]
    return name, headline


async def _profile_response(db: AsyncSession, user_id: UUID):
    cached = await cache.get_json("profile", str(user_id))
    if cached is not None:
        return cached

    profile = await get_profile_by_user(db, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    chunks = await list_evidence_by_profile(db, profile.id)
    response = {
        "id": str(profile.id),
        "tenant_id": str(profile.tenant_id),
        "full_name": profile.full_name,
        "headline": profile.headline,
        "location": profile.location,
        "timezone": profile.timezone,
        "raw_cv_md": profile.raw_cv_md,
        "profile_json": profile.profile_json,
        "evidence_chunks": [
            {
                "id": str(c.id),
                "source_type": c.source_type,
                "source_label": c.source_label,
                "content": c.content,
                "metadata_json": c.metadata_json,
            }
            for c in chunks
        ],
        "created_at": profile.created_at.isoformat() if profile.created_at else None,
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }
    await cache.set_json("profile", str(user_id), value=response)
    return response


async def _invalidate_profile_cache(user_id: UUID):
    await cache.delete("profile", str(user_id))


@router.get("", response_model=ProfileResponse | None)
async def get_profile(
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    if tenant.id is None or tenant.user_id is None:
        return None
    profile = await get_profile_by_user(db, tenant.user_id)
    if not profile:
        return None
    return await _profile_response(db, tenant.user_id)


@router.post("/import-url", response_model=ProfileResponse)
async def import_profile_from_url(
    body: URLImportRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    if tenant.id is None or tenant.user_id is None:
        raise HTTPException(status_code=400, detail="Tenant and user required")

    raw_text, metadata = await fetch_url_content(body.url)
    cv_md = await convert_to_cv_markdown(raw_text, body.url, tenant.id)

    name = metadata.get("name") or _parse_name_and_headline(cv_md)[0] or "Unknown"
    headline = metadata.get("headline") or _parse_name_and_headline(cv_md)[1] or "Unknown"
    location = metadata.get("location")
    profile = await upsert_profile(
        db,
        tenant.id,
        tenant.user_id,
        name,
        headline,
        cv_md,
        location=location,
    )
    profile.profile_json = {"source_url": body.url}

    await delete_evidence_by_profile(db, profile.id)
    chunks = chunk_cv_md(cv_md, profile.id, tenant.id)
    if chunks:
        await create_evidence_chunks(db, tenant.id, profile.id, chunks)

    await _invalidate_profile_cache(tenant.user_id)
    return await _profile_response(db, tenant.user_id)


@router.post("/import-pdf", response_model=ProfileResponse)
async def import_profile_from_pdf(
    file: UploadFile = File(...),
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    if tenant.id is None or tenant.user_id is None:
        raise HTTPException(status_code=400, detail="Tenant and user required")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    pdf_bytes = await file.read()
    raw_text = extract_pdf_text(pdf_bytes)
    cv_md = await convert_to_cv_markdown(raw_text, file.filename, tenant.id)

    name, headline = _parse_name_and_headline(cv_md)
    profile = await upsert_profile(
        db,
        tenant.id,
        tenant.user_id,
        name or "Unknown",
        headline or "Unknown",
        cv_md,
    )
    profile.profile_json = {"source_pdf": file.filename}

    await delete_evidence_by_profile(db, profile.id)
    chunks = chunk_cv_md(cv_md, profile.id, tenant.id)
    if chunks:
        await create_evidence_chunks(db, tenant.id, profile.id, chunks)

    await _invalidate_profile_cache(tenant.user_id)
    return await _profile_response(db, tenant.user_id)


@router.post("/cv", response_model=ProfileResponse)
async def upload_cv(
    body: CVUploadRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
):
    if tenant.id is None or tenant.user_id is None:
        raise HTTPException(status_code=400, detail="Tenant and user required")
    existing = await get_profile_by_user(db, tenant.user_id)
    name, headline = _parse_name_and_headline(body.raw_cv_md)
    name = name or (existing.full_name if existing else "Unknown")
    headline = headline or (existing.headline if existing else "Unknown")
    location = existing.location if existing else None
    profile = await upsert_profile(
        db,
        tenant.id,
        tenant.user_id,
        name,
        headline,
        body.raw_cv_md,
        location=location,
    )

    await delete_evidence_by_profile(db, profile.id)
    chunks = chunk_cv_md(body.raw_cv_md, profile.id, tenant.id)
    if chunks:
        await create_evidence_chunks(db, tenant.id, profile.id, chunks)

    await _invalidate_profile_cache(tenant.user_id)
    return await _profile_response(db, tenant.user_id)
