import re

from app.db.models import CandidateProfile, JobPosting, MatchReport
from app.modules.tracker.schemas import AutofillPayload


def generate_autofill_payload(
    profile: CandidateProfile | None,
    job: JobPosting | None,
    match_report: MatchReport | None,
    resume_link: str | None = None,
) -> AutofillPayload:
    name_parts = (profile.full_name if profile else "Demo User").split(" ", 1)
    first_name = name_parts[0] if name_parts else ""
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    return AutofillPayload(
        first_name=first_name,
        last_name=last_name,
        location=profile.location if profile and profile.location else "",
        current_employer=_extract_current_employer(profile.raw_cv_md)
        if profile and profile.raw_cv_md
        else "",
        years_of_experience=_extract_years_experience(profile.raw_cv_md)
        if profile and profile.raw_cv_md
        else 0,
        resume_link=resume_link or "",
        cover_note=_generate_cover_note(profile, match_report) if profile else "",
    )


def _extract_current_employer(cv_md: str) -> str:
    lines = cv_md.split("\n")
    for line in lines:
        if "—" in line or "–" in line:
            parts = line.split("—" if "—" in line else "–")
            employer_part = parts[0].strip()
            if "at" in employer_part.lower():
                employer = employer_part.split("at")[-1].strip()
                if employer:
                    return employer
            return employer_part
    return ""


def _extract_years_experience(cv_md: str) -> int:
    match = re.search(r"(\d+)\+?\s*years?\s*(?:of\s*)?experience", cv_md, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 0


def _generate_cover_note(profile: CandidateProfile | None, match_report: MatchReport | None) -> str:
    if not profile:
        return ""
    name = profile.full_name or "Candidate"
    note = "Dear Hiring Team,\n\nI am writing to express my interest in the position. "
    note += f"As a {profile.headline or 'professional'} with experience in {', '.join(_extract_top_skills(profile.raw_cv_md)[:3])}, "
    if match_report and match_report.explanation:
        note += "I believe my background aligns well with this role. "
    note += f"\n\nI have attached my CV for your review.\n\nBest regards,\n{name}"
    return note


def _extract_top_skills(cv_md: str) -> list[str]:
    skills_section = ""
    lines = cv_md.split("\n")
    in_skills = False
    for line in lines:
        if line.lower().startswith("## skills"):
            in_skills = True
            continue
        if in_skills and line.startswith("## "):
            break
        if in_skills:
            skills_section += line + " "
    if not skills_section:
        return []
    skills = [s.strip() for s in re.split(r"[,•\-;]", skills_section) if s.strip()]
    return skills[:10]
