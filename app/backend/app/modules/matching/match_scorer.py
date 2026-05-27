import json
import logging
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantContext
from app.db.models import MatchReport
from app.modules.jobs.repository import get_job
from app.modules.matching.jd_parser import parse_job_posting
from app.modules.matching.skill_taxonomy import (
    DACH_CITIES,
    DACH_COUNTRIES,
    GERMAN_KEYWORDS,
)
from app.modules.profiles.repository import get_profile_by_user


def _skill_overlap(jd_skills: list[str], profile_text: str) -> float:
    if not jd_skills:
        return 0.5
    profile_lower = profile_text.lower()
    matched = sum(1 for s in jd_skills if s.lower() in profile_lower)
    return matched / len(jd_skills)


def _dach_score(
    job_location: str | None,
    profile_location: str | None,
    jd_text: str,
    profile_text: str,
) -> float:
    score = 0.0
    jd_lower = jd_text.lower()
    profile_lower = profile_text.lower()

    loc_text = (job_location or "").lower()
    profile_loc_text = (profile_location or "").lower()

    job_in_dach = any(c in loc_text or c in jd_lower for c in DACH_CITIES)
    job_in_dach = job_in_dach or any(c in jd_lower for c in DACH_COUNTRIES)
    profile_in_dach = any(
        c in profile_loc_text or c in profile_lower for c in DACH_CITIES + DACH_COUNTRIES
    )

    if job_in_dach and profile_in_dach:
        score += 0.6
    elif job_in_dach:
        score += 0.2
    elif profile_in_dach:
        score += 0.3

    has_german = any(kw in jd_lower for kw in GERMAN_KEYWORDS)
    profile_has_german = any(kw in profile_lower for kw in GERMAN_KEYWORDS)
    if has_german and profile_has_german:
        score += 0.4
    elif has_german:
        score += 0.0
    elif profile_has_german:
        score += 0.2
    else:
        score += 0.3

    return min(score, 1.0)


def _extract_text_for_scoring(job) -> str:
    parts = [job.title or "", job.raw_jd or ""]
    if job.parsed_json:
        for key in ("must_have_skills", "nice_to_have_skills"):
            items = job.parsed_json.get(key, [])
            if isinstance(items, list):
                parts.extend(str(i) for i in items)
    return " ".join(parts)


def _calculate_score(job, profile):
    parsed = job.parsed_json or {}
    must_have = parsed.get("must_have_skills") or []

    jd_text = _extract_text_for_scoring(job)
    profile_text = f"{profile.headline or ''} {profile.raw_cv_md or ''} {json.dumps(profile.profile_json or {})}"

    role_relevance = _skill_overlap(
        [job.title or ""] + must_have,
        profile_text,
    )

    skill_match = _skill_overlap(must_have, profile_text)

    dach_feasibility = _dach_score(
        job.location,
        profile.location,
        jd_text,
        profile_text,
    )

    compensation_fit = 0.5
    if parsed.get("salary_range"):
        compensation_fit = 0.6

    growth_story_value = 0.5

    weights = {
        "role_relevance": 0.29,
        "skill_match": 0.36,
        "dach_feasibility": 0.21,
        "compensation_fit": 0.14,
    }

    breakdown = {
        "role_relevance": round(role_relevance * 5, 2),
        "skill_match": round(skill_match * 5, 2),
        "dach_feasibility": round(dach_feasibility * 5, 2),
        "compensation_fit": round(compensation_fit * 5, 2),
        "growth_story_value": round(growth_story_value * 5, 2),
    }

    overall = (
        role_relevance * weights["role_relevance"]
        + skill_match * weights["skill_match"]
        + dach_feasibility * weights["dach_feasibility"]
        + compensation_fit * weights["compensation_fit"]
    )

    overall_score = overall * 5.0
    overall_score = round(max(1.0, min(5.0, overall_score)), 2)

    if overall_score >= 4.2:
        recommendation = "apply"
    elif overall_score >= 3.6:
        recommendation = "maybe"
    else:
        recommendation = "skip"

    gaps = []
    if must_have:
        profile_lower = profile_text.lower()
        missing = [s for s in must_have if s.lower() not in profile_lower]
        if missing:
            gaps.append(f"Missing skills: {', '.join(missing[:5])}")

    parsed_german = any(kw in jd_text.lower() for kw in GERMAN_KEYWORDS)
    profile_german = any(kw in profile_text.lower() for kw in GERMAN_KEYWORDS)
    if parsed_german and not profile_german:
        gaps.append("German language requirement not met")

    return overall_score, recommendation, breakdown, {"gaps": gaps}


def _generate_explanation_template(
    overall_score: float,
    recommendation: str,
    breakdown: dict,
    gaps: dict | None,
) -> str:
    top = max(breakdown, key=breakdown.get)
    bottom = min(breakdown, key=breakdown.get)
    parts = [
        f"Overall match score: {overall_score}/5.0 — {recommendation}.",
        f"Strongest dimension: {top} ({breakdown[top]}/5).",
        f"Weakest dimension: {bottom} ({breakdown[bottom]}/5).",
    ]
    if gaps and gaps.get("gaps"):
        parts.append(f"Gaps identified: {'; '.join(gaps['gaps'])}.")
    return " ".join(parts)


async def compute_match(
    db: AsyncSession,
    tenant: TenantContext,
    job_id: uuid.UUID,
) -> MatchReport:
    job = await get_job(db, job_id, tenant.id)
    if not job:
        from app.core.errors import AppError

        raise AppError("job_not_found", "Job posting not found", status_code=404)

    if not job.parsed_json:
        await parse_job_posting(db, tenant, job)

    profile = await get_profile_by_user(db, tenant.user_id)
    if not profile:
        raise AppError("profile_not_found", "Candidate profile not found")

    overall_score, recommendation, breakdown, gaps = _calculate_score(job, profile)

    from app.modules.llm_gateway.gateway import LLMGateway

    logger = logging.getLogger(__name__)
    explanation = None
    gateway = LLMGateway()
    try:
        content = await gateway.run_text(
            tenant_id=tenant.id,
            task="fit_explanation",
            prompt_version="1.0",
            model_tier="fast",
            messages=[
                {
                    "role": "system",
                    "content": "You are a career coach. Given a match score and breakdown, write 2-3 sentences explaining the fit and key gaps. Be concise and factual.",
                },
                {
                    "role": "user",
                    "content": (
                        f"Score: {overall_score}/5. Recommendation: {recommendation}.\n"
                        f"Breakdown: {json.dumps(breakdown)}\n"
                        f"Gaps: {json.dumps(gaps)}\n"
                        f"Job: {job.title} at {job.company}\n"
                        f"Profile: {profile.headline}"
                    ),
                },
            ],
        )
        if content:
            explanation = content.strip()
    except Exception:
        logger.exception("LLM match explanation failed, falling back to template")

    if not explanation:
        explanation = _generate_explanation_template(
            overall_score,
            recommendation,
            breakdown,
            gaps,
        )

    report = MatchReport(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        job_id=job.id,
        overall_score=Decimal(str(overall_score)),
        recommendation=recommendation,
        breakdown_json=breakdown,
        gaps_json=gaps if gaps.get("gaps") else None,
        explanation=explanation,
    )
    db.add(report)
    await db.flush()
    return report
