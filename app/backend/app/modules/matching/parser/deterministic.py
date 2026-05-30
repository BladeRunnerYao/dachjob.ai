import re
from typing import Any

from app.modules.matching.parser.skills import (
    _extract_section,
    _extract_skills_from_text,
    extract_language_requirements,
)
from app.modules.matching.skill_taxonomy import (
    DACH_CITIES,
    DACH_COUNTRIES,
    GERMAN_KEYWORDS,
    NICE_TO_HAVE_SECTION_STARTS,
    SENIORITY_KEYWORDS,
    WORK_MODEL_KEYWORDS,
)


def deterministic_parse(job: Any) -> dict[str, Any]:
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

    lang_reqs = extract_language_requirements(job.raw_jd or "")

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
        "responsibilities": [],
        "required_qualifications": [],
        "preferred_qualifications": [],
        "raw_preview": job.raw_jd[:500] if job.raw_jd else "",
    }
