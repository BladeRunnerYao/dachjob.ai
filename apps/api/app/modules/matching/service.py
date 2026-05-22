import json
import re
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.tenant import TenantContext
from app.db.models import MatchReport, EvidenceChunk
from app.modules.jobs.repository import get_job
from app.modules.profiles.repository import get_profile_by_tenant

SKILL_KEYWORDS = [
    "python", "kubernetes", "docker", "fastapi", "redis", "postgresql",
    "terraform", "aws", "gcp", "azure", "mlflow", "airflow", "rust",
    "typescript", "react", "vue", "angular", "node", "go", "java",
    "spring", "sql", "mongodb", "kafka", "rabbitmq", "git", "ci/cd",
    "pytorch", "tensorflow", "scikit-learn", "pandas", "spark", "flink",
    "helm", "prometheus", "grafana", "datadog", "sentry", "docker compose",
    "graphql", "rest", "grpc", "redis", "celery", "nginx", "postgres",
    "mysql", "dynamodb", "s3", "lambda", "ecs", "eks", "ec2",
    "cloudformation", "pulumi", "jenkins", "github actions", "gitlab ci",
    "argocd", "istio", "envoy", "linkerd", "temporal", "prefect",
    "dbt", "bigquery", "snowflake", "databricks", "ray", "kubeflow",
]

SENIORITY_KEYWORDS = {
    "senior": "Senior",
    "lead": "Lead",
    "principal": "Principal",
    "staff": "Staff",
    "junior": "Junior",
    "graduate": "Graduate",
    "intern": "Intern",
    "head of": "Head",
    "manager": "Manager",
    "director": "Director",
    "vp": "VP",
    "chief": "Chief",
}

WORK_MODEL_KEYWORDS = {
    "remote": "remote",
    "fully remote": "remote",
    "100% remote": "remote",
    "hybrid": "hybrid",
    "onsite": "onsite",
    "on-site": "onsite",
    "in office": "onsite",
}

DACH_CITIES = [
    "berlin", "munich", "hamburg", "cologne", "frankfurt", "stuttgart",
    "düsseldorf", "leipzig", "dresden", "bonn", "zurich", "geneva",
    "bern", "basel", "lausanne", "vienna", "salzburg", "graz", "linz",
]

DACH_COUNTRIES = ["germany", "switzerland", "austria", "deutschland"]

GERMAN_KEYWORDS = [
    "german", "deutsch", "deutschkenntnisse", "fließend deutsch",
    "verhandlungssicher", "muttersprache",
]


def _deterministic_parse(job):
    jd_lower = job.raw_jd.lower() if job.raw_jd else ""
    title_lower = job.title.lower() if job.title else ""

    must_have = []
    nice_to_have = []
    for skill in SKILL_KEYWORDS:
        if skill in jd_lower or skill in title_lower:
            must_have.append(skill)

    work_model = "onsite"
    for keyword, model in WORK_MODEL_KEYWORDS.items():
        if keyword in jd_lower:
            work_model = model
            break

    seniority = None
    for keyword, level in SENIORITY_KEYWORDS.items():
        if keyword in title_lower or keyword in jd_lower:
            seniority = level
            break

    exp_match = re.search(r"(\d+)\+?\s*(?:years|yrs|years of experience)", jd_lower)
    experience_years = int(exp_match.group(1)) if exp_match else None

    salary_range = None
    salary_match = re.search(
        r"(?:€|eur|chf|usd)\s*([\d,.]+)\s*(?:k|000)?\s*(?:-|to|–)\s*(?:€|eur|chf|usd)?\s*([\d,.]+)\s*(?:k|000)?",
        jd_lower,
    )
    if salary_match:
        salary_range = f"{salary_match.group(1)}-{salary_match.group(2)}"

    location = job.location or ""
    dach_signals = {}
    for city in DACH_CITIES:
        if city in jd_lower or city in location.lower():
            dach_signals["location"] = city
            break
    for country in DACH_COUNTRIES:
        if country in jd_lower or country in location.lower():
            dach_signals["country"] = country
            break
    for kw in GERMAN_KEYWORDS:
        if kw in jd_lower:
            dach_signals["language"] = "german"
            break

    lang_reqs = []
    if "german" in jd_lower or "deutsch" in jd_lower:
        lang_reqs.append("German")
    if "english" in jd_lower:
        lang_reqs.append("English")

    return {
        "title": job.title,
        "company": job.company,
        "location": location,
        "work_model": work_model,
        "seniority": seniority,
        "experience_years": experience_years,
        "salary_range": salary_range,
        "must_have_skills": must_have,
        "nice_to_have_skills": nice_to_have,
        "language_requirements": lang_reqs,
        "dach_signals": dach_signals,
        "raw_preview": job.raw_jd[:500] if job.raw_jd else "",
    }


async def parse_job_posting(
    db: AsyncSession,
    tenant: TenantContext,
    job,
) -> dict:
    settings = get_settings()

    if settings.deepseek_api_key:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
            )
            response = await client.chat.completions.create(
                model=settings.deepseek_model_fast,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a job parser. Extract structured information from the job posting below. Return valid JSON only.",
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Title: {job.title}\n"
                            f"Company: {job.company}\n"
                            f"Location: {job.location or 'N/A'}\n"
                            f"Description:\n{job.raw_jd}\n\n"
                            "Extract JSON with these fields:\n"
                            "title, company, location, work_model (remote/hybrid/onsite), "
                            "language_requirements (list), must_have_skills (list), "
                            "nice_to_have_skills (list), responsibilities (list), "
                            "salary_range (string or null), seniority (string or null), "
                            "dach_signals (object with location/country/language keys)"
                        ),
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
                max_tokens=2000,
            )
            content = response.choices[0].message.content
            if content:
                parsed_json = json.loads(content)
                job.parsed_json = parsed_json
                job.status = "parsed"
                await db.flush()
                return {"status": "parsed", "parsed_json": parsed_json}
        except Exception:
            pass

    parsed_json = _deterministic_parse(job)
    job.parsed_json = parsed_json
    job.status = "parsed"
    await db.flush()
    return {"status": "parsed", "parsed_json": parsed_json}


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
    profile_in_dach = any(c in profile_loc_text or c in profile_lower for c in DACH_CITIES + DACH_COUNTRIES)

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


def _evidence_coverage(evidence_chunks: list, must_have_skills: list[str] | None) -> float:
    if not must_have_skills:
        return 0.5
    if not evidence_chunks:
        return 0.0
    combined = " ".join(c.content.lower() for c in evidence_chunks if c.content)
    matched = sum(1 for s in must_have_skills if s.lower() in combined)
    return matched / len(must_have_skills)


def _extract_text_for_scoring(job) -> str:
    parts = [job.title or "", job.raw_jd or ""]
    if job.parsed_json:
        for key in ("must_have_skills", "nice_to_have_skills", "responsibilities"):
            items = job.parsed_json.get(key, [])
            if isinstance(items, list):
                parts.extend(str(i) for i in items)
    return " ".join(parts)


def _calculate_score(job, profile, evidence_chunks):
    parsed = job.parsed_json or {}
    must_have = parsed.get("must_have_skills") or []

    jd_text = _extract_text_for_scoring(job)
    profile_text = f"{profile.headline or ''} {profile.raw_cv_md or ''} {json.dumps(profile.profile_json or {})}"

    role_relevance = _skill_overlap(
        [job.title or ""] + must_have,
        profile_text,
    )

    skill_match = _skill_overlap(must_have, profile_text)

    evidence_strength = _evidence_coverage(evidence_chunks, must_have)

    dach_feasibility = _dach_score(
        job.location, profile.location, jd_text, profile_text,
    )

    compensation_fit = 0.5
    if parsed.get("salary_range"):
        compensation_fit = 0.6

    growth_story_value = 0.5
    if evidence_chunks:
        labels = [c.source_label.lower() for c in evidence_chunks if c.source_label]
        progression_kw = ["senior", "lead", "promot", "advanc", "head of", "manager"]
        if any(any(kw in label for kw in progression_kw) for label in labels):
            growth_story_value = 0.7

    weights = {
        "role_relevance": 0.20,
        "skill_match": 0.25,
        "evidence_strength": 0.20,
        "dach_feasibility": 0.15,
        "compensation_fit": 0.10,
        "growth_story_value": 0.10,
    }

    breakdown = {
        "role_relevance": round(role_relevance * 5, 2),
        "skill_match": round(skill_match * 5, 2),
        "evidence_strength": round(evidence_strength * 5, 2),
        "dach_feasibility": round(dach_feasibility * 5, 2),
        "compensation_fit": round(compensation_fit * 5, 2),
        "growth_story_value": round(growth_story_value * 5, 2),
    }

    overall = (
        role_relevance * weights["role_relevance"]
        + skill_match * weights["skill_match"]
        + evidence_strength * weights["evidence_strength"]
        + dach_feasibility * weights["dach_feasibility"]
        + compensation_fit * weights["compensation_fit"]
        + growth_story_value * weights["growth_story_value"]
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
    job = await get_job(db, job_id)
    if not job:
        from app.core.errors import AppError
        raise AppError("job_not_found", "Job posting not found")

    profile = await get_profile_by_tenant(db, tenant.id)
    if not profile:
        raise AppError("profile_not_found", "Candidate profile not found for tenant")

    result = await db.execute(
        select(EvidenceChunk)
        .where(EvidenceChunk.profile_id == profile.id)
        .where(EvidenceChunk.tenant_id == tenant.id)
    )
    evidence_chunks = list(result.scalars().all())

    overall_score, recommendation, breakdown, gaps = _calculate_score(
        job, profile, evidence_chunks
    )

    settings = get_settings()
    explanation = None

    if settings.deepseek_api_key:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
            )
            resp = await client.chat.completions.create(
                model=settings.deepseek_model_fast,
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
                temperature=0.3,
                max_tokens=300,
            )
            content = resp.choices[0].message.content
            if content:
                explanation = content.strip()
        except Exception:
            pass

    if not explanation:
        explanation = _generate_explanation_template(
            overall_score, recommendation, breakdown, gaps,
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
