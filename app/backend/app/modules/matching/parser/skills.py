import re
from typing import Any

from app.modules.matching.skill_taxonomy import (
    MUST_HAVE_SECTION_STARTS,
    NICE_TO_HAVE_SECTION_STARTS,
    NON_SKILL_CANDIDATES,
    REQUIREMENT_SECTION_STOPS,
    SKILL_CITY_BLACKLIST,
    SKILL_LIST_TRIGGER_RE,
    SKILL_NAME_ALIASES,
    SKILL_PATTERNS,
    SKILL_SPLIT_RE,
    STRICT_WORK_AUTH_PATTERNS,
    SWISS_LOCATION_KEYWORDS,
    VISA_SPONSORSHIP_WARNING_PATTERNS,
    _dedupe_preserve_order,
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


def extract_language_requirements(raw_jd: str) -> list[str]:
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


def _is_swiss_job(job: Any) -> bool:
    text = f"{job.location or ''}\n{job.raw_jd or ''}".lower()
    return any(keyword in text for keyword in SWISS_LOCATION_KEYWORDS)


def _extract_work_authorization(job: Any) -> dict[str, str] | None:
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


def _enrich_parsed_skills(parsed_json: dict[str, Any], job: Any) -> dict[str, Any]:
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
