import json
import re
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.tenant import TenantContext
from app.db.models import MatchReport, EvidenceChunk
from app.modules.jobs.repository import get_job, sync_job_skills
from app.modules.profiles.repository import get_profile_by_tenant

SKILL_PATTERNS = [
    ("Python", [r"\bpython\b"]),
    ("TypeScript", [r"\btypescript\b"]),
    ("JavaScript", [r"\bjavascript\b"]),
    ("Node.js", [r"\bnode(?:\.js)?\b"]),
    ("React", [r"\breact\b"]),
    ("FastAPI", [r"\bfastapi\b"]),
    ("Go", [r"\bgolang\b", r"\bgo programming\b", r"\bgo language\b"]),
    ("Java", [r"\bjava\b"]),
    ("SQL", [r"\bsql\b"]),
    ("PostgreSQL", [r"\bpostgres(?:ql)?\b"]),
    ("MongoDB", [r"\bmongodb\b"]),
    ("Redis", [r"\bredis\b"]),
    ("Production databases", [r"production (?:database|databases|dbs)", r"databases in production"]),
    ("Database performance", [r"database performance", r"performance, scaling, and reliability"]),
    ("Docker", [r"\bdocker\b"]),
    ("Containerization", [r"\bcontaineri[sz]ed\b", r"\bcontaineri[sz]ation\b", r"container-based deployments?"]),
    ("Kubernetes", [r"\bkubernetes\b", r"\bk8s\b"]),
    ("GCP", [r"\bgcp\b", r"google cloud"]),
    ("Cloud Run", [r"\bcloud run\b"]),
    ("AWS", [r"\baws\b", r"amazon web services"]),
    ("Azure", [r"\bazure\b"]),
    ("Cloud infrastructure", [r"cloud infrastructure", r"infrastructure backbone"]),
    ("Cloud compute", [r"major cloud platform[^.\n]*compute", r"cloud[^.\n]*compute"]),
    ("Compute-intensive workloads", [r"compute-intensive workloads?"]),
    ("Scientific simulation workloads", [r"scientific simulation workloads?"]),
    ("Climate tech", [r"climate tech"]),
    ("Sustainability", [r"\bsustainability\b", r"\bsustainable\b"]),
    ("Built environment", [r"built environment"]),
    ("Cloud storage", [r"\bstorage\b"]),
    ("Networking", [r"\bnetworking\b", r"network architecture"]),
    ("IAM", [r"\biam\b", r"identity and access management"]),
    ("TLS", [r"\btls\b", r"\bssl\b"]),
    ("Firewall rules", [r"firewall rules?", r"\bfirewalls?\b"]),
    ("RBAC", [r"\brbac\b", r"role-based access control"]),
    ("Job queues", [r"job queues?", r"\bqueues?\b"]),
    ("Distributed workloads", [r"distributed workloads?"]),
    ("Event-driven architecture", [r"event-driven"]),
    ("Metrics", [r"\bmetrics\b"]),
    ("CI/CD pipelines", [r"\bci/cd\b", r"continuous integration", r"continuous deployment"]),
    ("GitHub Actions", [r"github actions"]),
    ("GitLab CI", [r"gitlab ci"]),
    ("Jenkins", [r"\bjenkins\b"]),
    ("Release management", [r"release process", r"release management", r"production deployment"]),
    ("Deployment workflows", [r"deployment workflows?", r"deployment process"]),
    ("Rollbacks", [r"\brollbacks?\b"]),
    ("Staging environments", [r"\bstaging\b"]),
    ("QA", [r"\bqa\b", r"quality assurance"]),
    ("E2E tests", [r"\be2e tests?\b", r"end-to-end tests?"]),
    ("Integration tests", [r"integration tests?"]),
    ("Developer experience", [r"developer experience", r"\bdx\b"]),
    ("On-call", [r"on-call", r"on call"]),
    ("Incident response", [r"incident response", r"severity processes?"]),
    ("Reliability engineering", [r"\breliability\b", r"ensure uptime", r"stable releases?"]),
    ("Observability", [r"\bobservability\b"]),
    ("Monitoring", [r"\bmonitoring\b"]),
    ("Vulnerability scanning", [r"vulnerability scanning"]),
    ("Penetration testing", [r"penetration testing", r"\bpentest(?:ing)?\b"]),
    ("Infrastructure hardening", [r"infrastructure hardening", r"security hardening"]),
    ("Infrastructure engineering", [r"infrastructure engineering"]),
    ("Platform engineering", [r"platform engineering"]),
    ("Backend engineering", [r"backend engineering", r"backend codebase"]),
    ("Data-oriented codebases", [r"data-oriented codebases?"]),
    ("Terraform", [r"\bterraform\b"]),
    ("Infrastructure as Code", [r"infrastructure-as-code", r"infrastructure as code", r"\biac\b"]),
    ("Ansible", [r"\bansible\b"]),
    ("Pulumi", [r"\bpulumi\b"]),
    ("Kafka", [r"\bkafka\b"]),
    ("RabbitMQ", [r"\brabbitmq\b"]),
    ("Airflow", [r"\bairflow\b"]),
    ("Dagster", [r"\bdagster\b"]),
    ("MLflow", [r"\bmlflow\b"]),
    ("PyTorch", [r"\bpytorch\b"]),
    ("TensorFlow", [r"\btensorflow\b"]),
    ("scikit-learn", [r"scikit-learn", r"\bsklearn\b"]),
    ("pandas", [r"\bpandas\b"]),
    ("Apache Spark", [r"apache spark", r"\bspark\b"]),
    ("Databricks", [r"\bdatabricks\b"]),
]

SKILL_KEYWORDS = [name for name, _patterns in SKILL_PATTERNS]

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

SWISS_LOCATION_KEYWORDS = [
    "switzerland", "swiss", "schweiz", "suisse", "svizzera", "zurich",
    "zürich", "zuerich", "geneva", "basel", "bern", "lausanne",
]

STRICT_WORK_AUTH_PATTERNS = [
    r"\b(?:only|must|require[sd]?|eligible|eligibility|applicants?|candidates?)\b.{0,140}\b(?:swiss|switzerland|schweiz|eu|e/u|efta|european union|swedish|sweden)\b.{0,140}\b(?:citizenship|citizens?|passport|work permit|right to work|work authori[sz]ation|eligible)\b",
    r"\b(?:swiss|switzerland|schweiz|eu|e/u|efta|european union|swedish|sweden)\b.{0,80}\b(?:citizenship|citizens?|passport holders?|work permit|right to work)\b.{0,80}\b(?:only|required|must|can't|cannot|unable|unfortunately)\b",
    r"\b(?:valid|existing)\b.{0,60}\b(?:swiss|switzerland|schweiz|eu|efta)\b.{0,60}\b(?:work permit|work authori[sz]ation|right to work)\b",
    r"\b(?:can't|cannot|unable to|unfortunately)\b.{0,120}\b(?:support|sponsor)\b.{0,120}\bnon[-\s]?eu\b",
]

VISA_SPONSORSHIP_WARNING_PATTERNS = [
    r"\b(?:no|not|unable to|cannot)\b.{0,80}\b(?:visa sponsorship|sponsor visas?|work permit sponsorship)\b",
    r"\b(?:must|need to)\b.{0,80}\b(?:already|currently)\b.{0,80}\b(?:authorized|eligible|right to work)\b",
]


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        cleaned = str(item).strip()
        if not cleaned:
            continue
        key = re.sub(r"\s+", " ", cleaned).strip(" .;:").casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def _extract_pattern_skills(text: str | None) -> list[str]:
    if not text:
        return []
    found: list[str] = []
    for name, patterns in SKILL_PATTERNS:
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
            found.append(name)
    return found


def _extract_section(raw_jd: str, start_keywords: tuple[str, ...], stop_keywords: tuple[str, ...]) -> str:
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
        if any(re.search(pattern, sentence, flags=re.IGNORECASE | re.DOTALL) for pattern in STRICT_WORK_AUTH_PATTERNS):
            return {
                "status": "restricted",
                "label": "Swiss/EU/EFTA eligibility restriction",
                "detail": "The posting appears to restrict applicants by citizenship, permit, or existing Swiss/EU/EFTA work authorization.",
                "evidence": sentence,
            }

    for sentence in sentences:
        if any(re.search(pattern, sentence, flags=re.IGNORECASE | re.DOTALL) for pattern in VISA_SPONSORSHIP_WARNING_PATTERNS):
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
        ("nice to have", "nice-to-have", "preferred", "bonus", "plus", "wünschenswert"),
        ("benefits", "what we offer", "about ", "show more", "seniority level"),
    )
    must_text = _extract_section(
        raw_jd,
        ("must have", "requirements", "who we are looking for", "what we look for"),
        ("nice to have", "benefits", "what this role is not", "show more", "seniority level"),
    )
    not_text = _extract_section(
        raw_jd,
        ("what this role is not", "this role is not"),
        ("requirements", "benefits", "must have", "nice to have"),
    )

    nice_skills = set(_extract_pattern_skills(nice_text))
    must_section_skills = set(_extract_pattern_skills(must_text))
    not_only_skills = set(_extract_pattern_skills(not_text)) - must_section_skills - nice_skills
    not_only_keys = {skill.casefold() for skill in not_only_skills}

    current_must = parsed_json.get("must_have_skills") if isinstance(parsed_json.get("must_have_skills"), list) else []
    current_must = [skill for skill in current_must if str(skill).casefold() not in not_only_keys]
    current_nice = parsed_json.get("nice_to_have_skills") if isinstance(parsed_json.get("nice_to_have_skills"), list) else []
    current_nice = [skill for skill in current_nice if str(skill).casefold() not in not_only_keys]
    inferred_skills = [
        skill for skill in _extract_pattern_skills(full_text)
        if skill not in not_only_skills
    ]

    enriched_nice = _dedupe_preserve_order(list(current_nice) + list(nice_skills))
    enriched_nice_keys = {skill.casefold() for skill in enriched_nice}
    enriched_must = _dedupe_preserve_order(
        list(current_must)
        + [skill for skill in inferred_skills if skill.casefold() not in enriched_nice_keys]
    )

    parsed_json["must_have_skills"] = enriched_must
    parsed_json["nice_to_have_skills"] = enriched_nice
    parsed_json["skills"] = _dedupe_preserve_order(enriched_must + enriched_nice)
    extracted_responsibilities = _extract_responsibilities(raw_jd)
    current_responsibilities = (
        parsed_json.get("responsibilities")
        if isinstance(parsed_json.get("responsibilities"), list)
        else []
    )
    parsed_json["responsibilities"] = (
        extracted_responsibilities
        if extracted_responsibilities
        else _dedupe_preserve_order(list(current_responsibilities))[:12]
    )
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

    must_have = _extract_pattern_skills(f"{job.title or ''}\n{job.raw_jd or ''}")
    nice_to_have = _extract_pattern_skills(
        _extract_section(
            job.raw_jd or "",
            ("nice to have", "nice-to-have", "preferred", "bonus", "plus", "wünschenswert"),
            ("benefits", "what we offer", "about ", "show more", "seniority level"),
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
        "responsibilities": _extract_responsibilities(job.raw_jd or ""),
        "language_requirements": lang_reqs,
        "dach_signals": dach_signals,
        "raw_preview": job.raw_jd[:500] if job.raw_jd else "",
    }


def _extract_responsibilities(raw_jd: str) -> list[str]:
    start_keywords = (
        "responsibilities",
        "tasks",
        "the impact you will have",
        "what you will do",
        "what you'll do",
        "your tasks",
        "aufgaben",
    )
    stop_keywords = (
        "what this role is not",
        "requirements",
        "must have",
        "who we are looking for",
        "nice to have",
        "benefits",
        "seniority level",
        "employment type",
        "job function",
        "industries",
        "show more",
    )
    heading_only = {
        "tasks",
        "responsibilities",
        "requirements",
        "benefits",
        "nice to have",
        "must have",
    }

    items: list[str] = []
    in_section = False
    for line in raw_jd.splitlines():
        stripped = line.strip()
        lower = stripped.lower()
        if not stripped:
            continue
        if in_section and any(key in lower for key in stop_keywords):
            break
        if any(key in lower for key in start_keywords):
            in_section = True
            continue
        if not in_section:
            continue
        if stripped.startswith("#"):
            break
        item = stripped.lstrip("-*• ").strip()
        item_lower = item.lower().strip(":")
        if item_lower in heading_only:
            continue
        if len(item) < 18:
            continue
        items.append(item)
    return _dedupe_preserve_order(items)[:12]


async def parse_job_posting(
    db: AsyncSession,
    tenant: TenantContext,
    job,
    force: bool = False,
) -> dict:
    if job.parsed_json and not force:
        await sync_job_skills(db, job, job.parsed_json, source="cached_parser")
        return {"status": job.status or "parsed", "parsed_json": job.parsed_json}

    settings = get_settings()

    api_key = settings.openrouter_api_key or settings.deepseek_api_key
    base_url = settings.openrouter_base_url if settings.openrouter_api_key else settings.deepseek_base_url
    model = settings.openrouter_model_fast if settings.openrouter_api_key else settings.deepseek_model_fast

    if api_key:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
            )
            response = await client.chat.completions.create(
                model=model,
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
                            "work_authorization (object or null with status, label, detail, evidence), "
                            "dach_signals (object with location/country/language/work_authorization keys)\n\n"
                            "Skill extraction rules:\n"
                            "- Extract atomic skills/capabilities, not only broad summary sentences.\n"
                            "- Include technologies, cloud services, infrastructure practices, security controls, testing/release practices, and operational responsibilities.\n"
                            "- Split combined requirements into separate items. Example: 'GCP infrastructure (Cloud Run, networking, IAM, TLS, firewall rules)' becomes "
                            "['GCP', 'Cloud Run', 'Networking', 'IAM', 'TLS', 'Firewall rules'].\n"
                            "- Treat capabilities like RBAC, job queues, CI/CD pipelines, GitHub Actions, E2E tests, QA, rollbacks, on-call, incident response, observability, monitoring, vulnerability scanning, penetration testing, and infrastructure hardening as skills when present.\n"
                            "- Do not include skills that are mentioned only in a negated section such as 'What this role is NOT'.\n"
                            "- Put explicit 'must have' requirements in must_have_skills and optional/preferred items in nice_to_have_skills.\n"
                            "- For Swiss jobs, flag explicit citizenship, work permit, EU/EFTA, right-to-work, or visa sponsorship restrictions in work_authorization with the exact evidence sentence."
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
                parsed_json = _enrich_parsed_skills(parsed_json, job)
                job.parsed_json = parsed_json
                job.status = "parsed"
                await sync_job_skills(db, job, parsed_json, source="deepseek")
                await db.flush()
                return {"status": "parsed", "parsed_json": parsed_json}
        except Exception:
            pass

    parsed_json = _enrich_parsed_skills(_deterministic_parse(job), job)
    job.parsed_json = parsed_json
    job.status = "parsed"
    await sync_job_skills(db, job, parsed_json, source="deterministic_parser")
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

    if not job.parsed_json:
        await parse_job_posting(db, tenant, job)

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

    api_key = settings.openrouter_api_key or settings.deepseek_api_key
    base_url = settings.openrouter_base_url if settings.openrouter_api_key else settings.deepseek_base_url
    model = settings.openrouter_model_fast if settings.openrouter_api_key else settings.deepseek_model_fast

    if api_key:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
            )
            resp = await client.chat.completions.create(
                model=model,
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
