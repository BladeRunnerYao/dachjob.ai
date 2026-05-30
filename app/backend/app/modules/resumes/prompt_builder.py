from typing import Any

from pydantic import BaseModel

from app.db.models import CandidateProfile


class ResumeOutput(BaseModel):
    html: str


def build_llm_prompt(
    profile: CandidateProfile,
    parsed_job: dict[str, Any],
    confirmed_skills: list[str] | None = None,
    style: str = "german",
) -> list[dict[str, str]]:
    cv_text = profile.raw_cv_md
    if style == "american":
        system_prompt = (
            "You are a US resume writer. Generate a one-page, ATS-friendly American resume "
            "as clean printable HTML with inline CSS. Use US letter proportions and a single-column layout. "
            "Use English section labels: Professional Summary, Professional Experience, Education, Technical Skills. "
            "Write concise achievement-focused bullets with impact and metrics when supported by the source CV. "
            "Never include a photo, date of birth, marital status, nationality, or full street address; use only city, email, phone, or links if present. "
            'Respond with valid JSON matching the schema: {"html": "<html>...</html>"}.'
        )
    else:
        system_prompt = (
            "You are a German/DACH CV writer for the German, Swiss, and Austrian job market. "
            "Generate a professional Lebenslauf/CV as clean printable HTML with inline CSS. Use A4 proportions, "
            "a polished sidebar plus main-column structure when possible, and a concise formal tone. "
            "Use sections for Profile, Berufserfahrung, Ausbildung, Skills/Qualifikationen, languages, and work authorization when present in the source CV. "
            "A professional photo is acceptable only if the source profile already provides one; otherwise do not invent one. "
            "Keep birth date or marital status out unless explicitly present and useful for the target market. "
            'Respond with valid JSON matching the schema: {"html": "<html>...</html>"}.'
        )
    confirmed_note = ""
    if confirmed_skills:
        confirmed_note = (
            "\n\nIMPORTANT: The candidate has manually confirmed they possess the following skills. "
            f"Make sure these are prominently featured in the Skills section and woven into the Professional Summary: "
            f"{', '.join(confirmed_skills)}"
        )
    user_prompt = (
        f"Requested CV style: {style}\n\n"
        f"Job requirements:\n{parsed_job}\n\n"
        f"Candidate profile:\nName: {profile.full_name}\nHeadline: {profile.headline}\n\n"
        f"CV:\n{cv_text}"
        f"{confirmed_note}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
