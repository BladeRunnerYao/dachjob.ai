from typing import Any

from pydantic import BaseModel

from app.db.models import CandidateProfile


class ResumeOutput(BaseModel):
    html: str


def build_llm_prompt(
    profile: CandidateProfile,
    parsed_job: dict[str, Any],
    confirmed_skills: list[str] | None = None,
) -> list[dict[str, str]]:
    cv_text = profile.raw_cv_md
    system_prompt = (
        "You are a DACH-format resume writer for the German/Swiss/Austrian job market. "
        "Generate a professional resume HTML that is clean, printable, and uses inline CSS. "
        "Follow this structure: Name and contact header, Professional Summary, "
        "Berufserfahrung (Professional Experience), Skills/Qualifikationen, Education/Ausbildung. "
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
        f"Job requirements:\n{parsed_job}\n\n"
        f"Candidate profile:\nName: {profile.full_name}\nHeadline: {profile.headline}\n\n"
        f"CV:\n{cv_text}"
        f"{confirmed_note}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
