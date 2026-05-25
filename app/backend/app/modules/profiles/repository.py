from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CandidateProfile, EvidenceChunk


async def get_profile_by_user(db: AsyncSession, user_id: UUID) -> CandidateProfile | None:
    result = await db.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == user_id).limit(1)
    )
    return result.scalar_one_or_none()


async def upsert_profile(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    full_name: str,
    headline: str,
    raw_cv_md: str,
    location: str | None = None,
) -> CandidateProfile:
    profile = await get_profile_by_user(db, user_id)
    if profile:
        profile.raw_cv_md = raw_cv_md
        profile.full_name = full_name
        profile.headline = headline
        if location is not None:
            profile.location = location
    else:
        profile = CandidateProfile(
            tenant_id=tenant_id,
            user_id=user_id,
            full_name=full_name,
            headline=headline,
            raw_cv_md=raw_cv_md,
            location=location,
        )
        db.add(profile)
    await db.flush()
    return profile


async def list_evidence_by_profile(db: AsyncSession, profile_id: UUID) -> list[EvidenceChunk]:
    result = await db.execute(
        select(EvidenceChunk)
        .where(EvidenceChunk.profile_id == profile_id)
        .order_by(EvidenceChunk.created_at)
    )
    return list(result.scalars().all())


async def create_evidence_chunks(
    db: AsyncSession, tenant_id: UUID, profile_id: UUID, chunks: list[dict]
) -> list[EvidenceChunk]:
    created = []
    for c in chunks:
        chunk = EvidenceChunk(
            tenant_id=tenant_id,
            profile_id=profile_id,
            source_type=c["source_type"],
            source_label=c["source_label"],
            content=c["content"],
            metadata_json=c.get("metadata_json"),
        )
        db.add(chunk)
        created.append(chunk)
    await db.flush()
    return created


async def delete_evidence_by_profile(db: AsyncSession, profile_id: UUID) -> None:
    result = await db.execute(select(EvidenceChunk).where(EvidenceChunk.profile_id == profile_id))
    for chunk in result.scalars().all():
        await db.delete(chunk)
    await db.flush()
