import re
import uuid
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantContext
from app.db.models import CandidateProfile, MatchReport, ResumeArtifact
from app.modules.jobs.repository import get_job
from app.modules.llm_gateway.gateway import LLMGateway
from app.modules.storage.service import StorageService


async def create_resume_artifact(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    job_id: uuid.UUID,
    html_object_key: str,
    provenance: dict | None = None,
    user_id: uuid.UUID | None = None,
) -> ResumeArtifact:
    artifact = ResumeArtifact(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        job_id=job_id,
        html_object_key=html_object_key,
        provenance_json=provenance or {},
    )
    db.add(artifact)
    await db.flush()
    return artifact


class _ResumeOutput(BaseModel):
    html: str


def _profile_query_for_resume(tenant: TenantContext):
    query = select(CandidateProfile).where(CandidateProfile.tenant_id == tenant.id)
    if tenant.user_id is not None:
        query = query.where(CandidateProfile.user_id == tenant.user_id)
    return query.limit(1)


async def generate_resume(
    db: AsyncSession, tenant: TenantContext, job_id: uuid.UUID
) -> ResumeArtifact:
    job = await get_job(db, job_id, tenant.id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    profile_result = await db.execute(_profile_query_for_resume(tenant))
    profile = profile_result.scalar_one_or_none()
    if not profile:
        raise ValueError("No profile found for the authenticated user")

    parsed_job = job.parsed_json or {"title": job.title, "company": job.company, "raw": job.raw_jd}

    html: str | None = None
    provenance: dict[str, Any] = {"method": "template", "job_id": str(job_id)}

    try:
        gateway = LLMGateway()
        messages = _build_llm_prompt(profile, parsed_job)
        result = await gateway.run_json(
            tenant_id=tenant.id,
            task="resume_generate",
            prompt_version="1.0",
            model_tier="quality",
            messages=messages,
            output_schema=_ResumeOutput,
            thinking=False,
        )
        html = result.html
        provenance = {
            "method": "llm",
            "job_id": str(job_id),
            "provider": gateway.last_provider,
            "model": gateway.last_model,
        }
    except Exception:
        pass

    if not html:
        html, prov = _generate_html_resume(profile, parsed_job)
        provenance = {**provenance, **prov}

    storage = StorageService()
    file_id = uuid.uuid4()

    html_object_key = f"resumes/{job_id}/{file_id}.html"
    storage.upload(html_object_key, html.encode("utf-8"), content_type="text/html; charset=utf-8")

    pdf_bytes = _html_to_pdf(html)
    pdf_object_key = f"resumes/{job_id}/{file_id}.pdf"
    storage.upload(pdf_object_key, pdf_bytes, content_type="application/pdf")

    match_result = await db.execute(
        select(MatchReport)
        .where(
            MatchReport.job_id == job_id,
            MatchReport.tenant_id == tenant.id,
        )
        .order_by(MatchReport.created_at.desc())
        .limit(1)
    )
    match_report = match_result.scalar_one_or_none()

    artifact = ResumeArtifact(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        user_id=tenant.user_id,
        job_id=job_id,
        match_report_id=match_report.id if match_report else None,
        html_object_key=html_object_key,
        pdf_object_key=pdf_object_key,
        provenance_json=provenance,
    )
    db.add(artifact)
    await db.flush()
    return artifact


def _build_llm_prompt(
    profile: CandidateProfile,
    parsed_job: dict,
) -> list[dict]:
    cv_text = profile.raw_cv_md
    system_prompt = (
        "You are a DACH-format resume writer for the German/Swiss/Austrian job market. "
        "Generate a professional resume HTML that is clean, printable, and uses inline CSS. "
        "Follow this structure: Name and contact header, Professional Summary, "
        "Berufserfahrung (Professional Experience), Skills/Qualifikationen, Education/Ausbildung. "
        'Respond with valid JSON matching the schema: {"html": "<html>...</html>"}.'
    )
    user_prompt = (
        f"Job requirements:\n{parsed_job}\n\n"
        f"Candidate profile:\nName: {profile.full_name}\nHeadline: {profile.headline}\n\n"
        f"CV:\n{cv_text}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _generate_html_resume(
    profile: CandidateProfile,
    parsed_job: dict,
) -> tuple[str, list[dict]]:
    job_title = (
        parsed_job.get("title", profile.headline)
        if isinstance(parsed_job, dict)
        else profile.headline
    )
    company = parsed_job.get("company", "") if isinstance(parsed_job, dict) else ""

    cv_text = profile.raw_cv_md or ""

    summary_parts: list[str] = []
    skills: list[str] = []
    experience_items: list[str] = []
    education_items: list[str] = []

    section_pattern = re.compile(r"^## (.+)$", re.MULTILINE)
    boundaries = []
    for m in section_pattern.finditer(cv_text):
        boundaries.append(m.start())
    boundaries.append(len(cv_text))

    section_names = [m.group(1).strip() for m in section_pattern.finditer(cv_text)]

    for i, name in enumerate(section_names):
        start = boundaries[i]
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(cv_text)
        section_text = cv_text[start:end].strip()
        name_lower = name.lower()

        content_no_heading = re.sub(
            r"^##\s+.+$", "", section_text, count=1, flags=re.MULTILINE
        ).strip()

        if "summary" in name_lower or "profil" in name_lower or "zusammenfassung" in name_lower:
            summary_parts.append(content_no_heading)
        elif "skill" in name_lower or "qualifikation" in name_lower or "kompetenz" in name_lower:
            for line in content_no_heading.split("\n"):
                line = line.strip().lstrip("-*").strip()
                if line:
                    skills.append(line)
        elif (
            "education" in name_lower
            or "ausbildung" in name_lower
            or "bildung" in name_lower
            or "studium" in name_lower
        ):
            for line in content_no_heading.split("\n"):
                line = line.strip().lstrip("-*").strip()
                if line:
                    education_items.append(line)
        elif (
            "experience" in name_lower
            or "erfahrung" in name_lower
            or "berufserfahrung" in name_lower
            or "career" in name_lower
        ):
            for line in content_no_heading.split("\n"):
                line = line.strip().lstrip("-*").strip()
                if line:
                    experience_items.append(line)

    summary_html = f"<p>{summary_parts[0][:500]}</p>" if summary_parts else ""
    skills_html = "".join(f"<li>{s[:200]}</li>" for s in skills[:15]) if skills else ""
    exp_html = "".join(f"<li>{e}</li>" for e in experience_items[:10])
    edu_html = "".join(f"<li>{e}</li>" for e in education_items[:5])

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 11pt; color: #222; margin: 0; padding: 0; line-height: 1.5; }}
  .page {{ max-width: 210mm; margin: 0 auto; padding: 20mm 15mm; }}
  h1 {{ font-size: 22pt; margin: 0 0 2pt 0; color: #1a1a1a; }}
  .headline {{ font-size: 13pt; color: #555; margin-bottom: 8pt; }}
  .contact {{ font-size: 10pt; color: #666; margin-bottom: 16pt; }}
  h2 {{ font-size: 14pt; border-bottom: 1.5px solid #1a1a1a; padding-bottom: 3pt; margin: 18pt 0 8pt 0; color: #1a1a1a; }}
  ul {{ margin: 4pt 0 8pt 0; padding-left: 18pt; }}
  li {{ margin-bottom: 3pt; }}
  .section {{ page-break-inside: avoid; }}
</style>
</head>
<body>
<div class="page">
  <h1>{profile.full_name}</h1>
  <div class="headline">{job_title}{f" &mdash; {company}" if company else ""}</div>
  <div class="contact">{profile.location or ""}{" | " if profile.location else ""}{profile.timezone or ""}</div>

  <div class="section">
    <h2>Professional Summary</h2>
    {summary_html}
  </div>

  <div class="section">
    <h2>Berufserfahrung</h2>
    <ul>{exp_html}</ul>
  </div>

  {f'<div class="section"><h2>Qualifikationen &amp; Skills</h2><ul>{skills_html}</ul></div>' if skills_html else ""}

  <div class="section">
    <h2>Ausbildung</h2>
    <ul>{edu_html if edu_html else "<li>Details available upon request</li>"}</ul>
  </div>
</div>
</body>
</html>"""

    provenance: list[dict] = []
    return html, provenance


def _html_to_pdf(html: str) -> bytes:
    from weasyprint import HTML

    return HTML(string=html).write_pdf()
