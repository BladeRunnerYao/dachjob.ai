from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CandidateProfile


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
