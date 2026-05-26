import json
import logging
import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantContext
from app.modules.jobs.repository import sync_job_skills
from app.modules.matching.skill_taxonomy import (
    _dedupe_preserve_order,
    DACH_CITIES,
    DACH_COUNTRIES,
    GERMAN_KEYWORDS,
    MUST_HAVE_SECTION_STARTS,
    NICE_TO_HAVE_SECTION_STARTS,
    NON_SKILL_CANDIDATES,
    REQUIREMENT_SECTION_STOPS,
    SENIORITY_KEYWORDS,
    SKILL_CITY_BLACKLIST,
    SKILL_LIST_TRIGGER_RE,
    SKILL_NAME_ALIASES,
    SKILL_PATTERNS,
    SKILL_SPLIT_RE,
    STRICT_WORK_AUTH_PATTERNS,
    SWISS_LOCATION_KEYWORDS,
    VISA_SPONSORSHIP_WARNING_PATTERNS,
    WORK_MODEL_KEYWORDS,
)


def _extract_pattern_skills(text: str | None) -> list[str]:
    if not text:
        return []
    found: list[str] = []
    for name, patterns in SKILL_PATTERNS:
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
            found.append(name)
    return found


def _normalize_skill_candidate(value: str) -> str | None:
    cleaned = re.sub(r"\s+", " ", value).strip(" \t\n\r.,;:()[]{}")
    cleaned = re.sub(
        r"^(?:tools?|frameworks?|platforms?|languages?)\s+(?:such as|like)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = cleaned.strip(" \t\n\r.,;:()[]{}")
    if not cleaned:
        return None
    lowered = cleaned.casefold()
    if re.search(r"https?://|www\.", lowered):
        return None
    if lowered in NON_SKILL_CANDIDATES:
        return None
    words = re.findall(r"[A-Za-z0-9+#./-]+", cleaned)
    if len(words) > 4:
        return None
    if re.search(
        r"\b(?:please|visit|role|candidate|candidates|team|company|office|"
        r"opportunity|parents-to-be|to work|we work|we|you|your|our|this)\b",
        lowered,
    ):
        return None
    if len(cleaned) > 60 or len(cleaned) < 2:
        return None
    if re.search(
        r"\b(?:experience|familiarity|knowledge|ability|skills?|systems?)\s*$",
        cleaned,
        flags=re.IGNORECASE,
    ):
        return None
    if lowered in SKILL_NAME_ALIASES:
        return SKILL_NAME_ALIASES[lowered]
    if cleaned[0].islower():
        return None
    if re.fullmatch(r"[A-Z][A-Za-z0-9+#./-]{1,20}", cleaned):
        return cleaned
    if re.fullmatch(r"[A-Z]{2,}(?:/[A-Z0-9]+)?", cleaned):
        return cleaned
    if re.search(r"[A-Z][a-z]+(?:\.[A-Za-z]+)?|[A-Z]{2,}|[0-9]|[+#/.-]", cleaned):
        return cleaned
    return None


def _split_skill_segment(segment: str) -> list[str]:
    segment = re.sub(r"\betc\.?.*$", "", segment, flags=re.IGNORECASE)
    segment = re.sub(r"\bsimilar\b.*$", "", segment, flags=re.IGNORECASE)
    parts = SKILL_SPLIT_RE.split(segment)
    candidates: list[str] = []
    for part in parts:
        candidate = _normalize_skill_candidate(part)
        if candidate:
            candidates.append(candidate)
    return candidates


def _extract_listed_skills(text: str | None) -> list[str]:
    if not text:
        return []
    candidates: list[str] = []
    for line in text.splitlines():
        for match in SKILL_LIST_TRIGGER_RE.finditer(line):
            candidates.extend(_split_skill_segment(match.group(1)))
    return _dedupe_preserve_order(candidates)


def _extract_skills_from_text(text: str | None) -> list[str]:
    return _dedupe_preserve_order(_extract_pattern_skills(text) + _extract_listed_skills(text))


def _extract_section(
    raw_jd: str, start_keywords: tuple[str, ...], stop_keywords: tuple[str, ...]
) -> str:
    lines = raw_jd.splitlines()
    section: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        lower = stripped.lower()
        if not stripped:
            continue
        if in_section and any(stop in lower for stop in stop_keywords):
            break
        if any(start in lower for start in start_keywords):
            in_section = True
            continue
        if in_section:
            section.append(stripped)
    return "\n".join(section)


def _extract_language_requirements(raw_jd: str) -> list[str]:
    requirements: list[str] = []
    language_patterns = {
        "English": [
            r"english.{0,80}(?:required|proficiency|fluent|communication|written|verbal|skills)",
            r"(?:required|proficiency|fluent|communication|written|verbal|skills).{0,80}english",
        ],
        "German": [
            r"german.{0,80}(?:required|proficiency|fluent|communication|written|verbal|skills)",
            r"deutsch.{0,80}(?:erforderlich|kenntnisse|fließend|kommunikation)",
            r"(?:required|proficiency|fluent|communication|written|verbal|skills).{0,80}german",
        ],
    }
    for language, patterns in language_patterns.items():
        if any(re.search(pattern, raw_jd, flags=re.IGNORECASE | re.DOTALL) for pattern in patterns):
            requirements.append(language)
    return requirements


def _sentences(text: str) -> list[str]:
    normalized = re.sub(r"\r\n?", "\n", text or "")
    parts = re.split(r"(?<=[.!?])\s+|\n+", normalized)
    return [re.sub(r"\s+", " ", part).strip() for part in parts if len(part.strip()) > 12]


def _is_swiss_job(job) -> bool:
    text = f"{job.location or ''}\n{job.raw_jd or ''}".lower()
    return any(keyword in text for keyword in SWISS_LOCATION_KEYWORDS)


def _extract_work_authorization(job) -> dict | None:
    if not _is_swiss_job(job):
        return None

    text = f"{job.title or ''}\n{job.company or ''}\n{job.location or ''}\n{job.raw_jd or ''}"
    sentences = _sentences(text)
    for sentence in sentences:
        if any(
            re.search(pattern, sentence, flags=re.IGNORECASE | re.DOTALL)
            for pattern in STRICT_WORK_AUTH_PATTERNS
        ):
            return {
                "status": "restricted",
                "label": "Swiss/EU/EFTA eligibility restriction",
                "detail": "The posting appears to restrict applicants by citizenship, permit, or existing Swiss/EU/EFTA work authorization.",
                "evidence": sentence,
            }

    for sentence in sentences:
        if any(
            re.search(pattern, sentence, flags=re.IGNORECASE | re.DOTALL)
            for pattern in VISA_SPONSORSHIP_WARNING_PATTERNS
        ):
            return {
                "status": "warning",
                "label": "Visa sponsorship warning",
                "detail": "The posting may require existing local work authorization.",
                "evidence": sentence,
            }

    return None


def _enrich_parsed_skills(parsed_json: dict, job) -> dict:
    raw_jd = job.raw_jd or ""
    title = job.title or ""
    full_text = f"{title}\n{raw_jd}"
    nice_text = _extract_section(
        raw_jd,
        NICE_TO_HAVE_SECTION_STARTS,
        ("benefits", "what we offer", "how to apply", "about ", "show more", "seniority level"),
    )
    must_text = _extract_section(
        raw_jd,
        MUST_HAVE_SECTION_STARTS,
        REQUIREMENT_SECTION_STOPS + ("what this role is not",),
    )
    not_text = _extract_section(
        raw_jd,
        ("what this role is not", "this role is not"),
        ("requirements", "benefits", "must have", "nice to have"),
    )

    nice_section_skills = _extract_skills_from_text(nice_text)
    must_section_skills = _extract_skills_from_text(must_text)
    not_only_skills = (
        set(_extract_skills_from_text(not_text))
        - set(must_section_skills)
        - set(nice_section_skills)
    )
    not_only_keys = {skill.casefold() for skill in not_only_skills}

    current_must = (
        parsed_json.get("must_have_skills")
        if isinstance(parsed_json.get("must_have_skills"), list)
        else []
    )
    current_must = [skill for skill in current_must if str(skill).casefold() not in not_only_keys]
    current_nice = (
        parsed_json.get("nice_to_have_skills")
        if isinstance(parsed_json.get("nice_to_have_skills"), list)
        else []
    )
    current_nice = [skill for skill in current_nice if str(skill).casefold() not in not_only_keys]
    inferred_skills = [
        skill for skill in _extract_skills_from_text(full_text) if skill not in not_only_skills
    ]

    must_seed = _dedupe_preserve_order(list(current_must) + must_section_skills)
    must_seed_keys = {skill.casefold() for skill in must_seed}
    nice_seed = _dedupe_preserve_order(
        [
            skill
            for skill in list(current_nice) + nice_section_skills
            if str(skill).casefold() not in must_seed_keys
        ]
    )
    nice_seed_keys = {skill.casefold() for skill in nice_seed}
    enriched_must = _dedupe_preserve_order(
        must_seed + [skill for skill in inferred_skills if skill.casefold() not in nice_seed_keys]
    )
    enriched_must_keys = {skill.casefold() for skill in enriched_must}
    enriched_nice = _dedupe_preserve_order(
        [skill for skill in nice_seed if skill.casefold() not in enriched_must_keys]
    )

    enriched_must = [s for s in enriched_must if s.casefold() not in SKILL_CITY_BLACKLIST]
    enriched_nice = [s for s in enriched_nice if s.casefold() not in SKILL_CITY_BLACKLIST]

    parsed_json["must_have_skills"] = enriched_must
    parsed_json["nice_to_have_skills"] = enriched_nice
    parsed_json["skills"] = _dedupe_preserve_order(enriched_must + enriched_nice)
    work_authorization = _extract_work_authorization(job)
    if work_authorization:
        parsed_json["work_authorization"] = work_authorization
        dach_signals = parsed_json.get("dach_signals")
        if not isinstance(dach_signals, dict):
            dach_signals = {}
        dach_signals["work_authorization"] = work_authorization["label"]
        parsed_json["dach_signals"] = dach_signals
    return parsed_json


def _deterministic_parse(job):
    jd_lower = job.raw_jd.lower() if job.raw_jd else ""
    title_lower = job.title.lower() if job.title else ""

    must_have = _extract_skills_from_text(f"{job.title or ''}\n{job.raw_jd or ''}")
    nice_to_have = _extract_skills_from_text(
        _extract_section(
            job.raw_jd or "",
            NICE_TO_HAVE_SECTION_STARTS,
            ("benefits", "what we offer", "how to apply", "about ", "show more", "seniority level"),
        )
    )
    nice_keys = {skill.casefold() for skill in nice_to_have}
    must_have = [skill for skill in must_have if skill.casefold() not in nice_keys]

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
    location_lower = location.lower()
    for country in DACH_COUNTRIES:
        if country in location_lower:
            dach_signals["country"] = country
            break
    if "country" not in dach_signals:
        for country in DACH_COUNTRIES:
            if country in jd_lower:
                dach_signals["country"] = country
                break
    for kw in GERMAN_KEYWORDS:
        if kw in jd_lower:
            dach_signals["language"] = "german"
            break

    lang_reqs = _extract_language_requirements(job.raw_jd or "")

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
        "skills": must_have + nice_to_have,
        "language_requirements": lang_reqs,
        "dach_signals": dach_signals,
        "raw_preview": job.raw_jd[:500] if job.raw_jd else "",
    }


def _jd_extract_messages(job) -> list[dict]:
    return [
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
                "nice_to_have_skills (list), "
                "salary_range (string or null), seniority (string or null), "
                "work_authorization (object or null with status, label, detail, evidence), "
                "dach_signals (object with location/country/language/work_authorization keys)\n\n"
                "Skill extraction rules:\n"
                "- Extract as many explicit atomic skills/capabilities as the posting contains, not only broad summary sentences.\n"
                "- Include programming languages, frameworks, databases, protocols, cloud services, infrastructure practices, security controls, testing/release practices, domain capabilities, collaboration requirements, and operational responsibilities.\n"
                "- Split combined requirements into separate items. Example: 'GCP infrastructure (Cloud Run, networking, IAM, TLS, firewall rules)' becomes "
                "['GCP', 'Cloud Run', 'Networking', 'IAM', 'TLS', 'Firewall rules'].\n"
                "- Treat capabilities like RBAC, job queues, CI/CD pipelines, GitHub Actions, E2E tests, QA, rollbacks, on-call, incident response, observability, monitoring, vulnerability scanning, penetration testing, and infrastructure hardening as skills when present.\n"
                "- Put skills from sections like 'Requirements', 'Your toolkit', 'What you must have', or equivalent in must_have_skills.\n"
                "- Put skills from sections like 'Nice to have', 'Preferred', 'Bonus', 'Extras that give you an edge', or equivalent in nice_to_have_skills.\n"
                "- Do not include skills that are mentioned only in a negated section such as 'What this role is NOT'.\n"
                "- Do NOT extract city names, office locations, or company headquarters as skills (e.g. Stockholm, London, New York). These are locations, not skills.\n"
                "- Put explicit 'must have' requirements in must_have_skills and optional/preferred items in nice_to_have_skills.\n"
                "- For Swiss jobs, flag explicit citizenship, work permit, EU/EFTA, right-to-work, or visa sponsorship restrictions in work_authorization with the exact evidence sentence."
            ),
        },
    ]


def _needs_reasoning_parse_retry(parsed_json: dict, job) -> bool:
    raw_jd = job.raw_jd or ""
    skill_count = len(parsed_json.get("must_have_skills") or []) + len(
        parsed_json.get("nice_to_have_skills") or []
    )
    has_requirement_signal = any(
        signal in raw_jd.lower()
        for signal in (
            "requirements",
            "your toolkit",
            "what you must have",
            "must have",
            "qualifications",
            "your mission",
        )
    )
    return len(raw_jd) > 1200 and has_requirement_signal and skill_count < 4


async def parse_job_posting(
    db: AsyncSession,
    tenant: TenantContext,
    job,
    force: bool = False,
) -> dict:
    logger = logging.getLogger(__name__)

    if job.parsed_json and not force:
        await sync_job_skills(db, job, job.parsed_json, source="cached_parser")
        logger.info("parse_cache_hit | job_id=%s tenant_id=%s", job.id, tenant.id)
        try:
            from app.db.models import LLMRun

            run = LLMRun(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                task="jd_extract",
                provider="cache",
                model="cache",
                prompt_version="1.1",
                latency_ms=0,
                status="cache_hit",
            )
            db.add(run)
            await db.flush()
        except Exception:
            pass
        return {"status": job.status or "parsed", "parsed_json": job.parsed_json}

    from app.modules.llm_gateway.gateway import LLMGateway

    gateway = LLMGateway()
    messages = _jd_extract_messages(job)
    try:
        content = await gateway.run_text(
            tenant_id=tenant.id,
            task="jd_extract",
            prompt_version="1.1",
            model_tier="quality",
            messages=messages,
            response_format={"type": "json_object"},
        )
        if content:
            parsed_json = json.loads(content)
            parsed_json = _enrich_parsed_skills(parsed_json, job)
            if _needs_reasoning_parse_retry(parsed_json, job):
                try:
                    retry_content = await gateway.run_text(
                        tenant_id=tenant.id,
                        task="jd_extract",
                        prompt_version="1.1-reasoning-retry",
                        messages=messages,
                        reasoning=True,
                        response_format={"type": "json_object"},
                    )
                    if retry_content:
                        retry_json = _enrich_parsed_skills(json.loads(retry_content), job)
                        if len(retry_json.get("skills") or []) > len(
                            parsed_json.get("skills") or []
                        ):
                            parsed_json = retry_json
                except Exception:
                    logger.exception("Reasoning model JD parse retry failed, keeping fast parse")
            job.parsed_json = parsed_json
            job.status = "parsed"
            await sync_job_skills(db, job, parsed_json, source=gateway.last_provider)
            await db.flush()
            return {"status": "parsed", "parsed_json": parsed_json}
    except Exception:
        logger.exception("LLM job parsing failed, falling back to deterministic parser")

    parsed_json = _enrich_parsed_skills(_deterministic_parse(job), job)
    job.parsed_json = parsed_json
    job.status = "parsed"
    await sync_job_skills(db, job, parsed_json, source="deterministic_parser")
    await db.flush()
    return {"status": "parsed", "parsed_json": parsed_json}
