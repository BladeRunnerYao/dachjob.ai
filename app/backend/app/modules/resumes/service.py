import re
import uuid
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantContext
from app.db.models import CandidateProfile, EvidenceChunk, MatchReport, ResumeArtifact
from app.modules.jobs.repository import get_job
from app.modules.llm_gateway.gateway import LLMGateway
from app.modules.storage.service import StorageService


async def list_evidence(
    db: AsyncSession, tenant_id: uuid.UUID, profile_id: uuid.UUID
) -> list[EvidenceChunk]:
    result = await db.execute(
        select(EvidenceChunk)
        .where(
            EvidenceChunk.tenant_id == tenant_id,
            EvidenceChunk.profile_id == profile_id,
        )
        .order_by(EvidenceChunk.created_at)
    )
    return list(result.scalars().all())


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


def chunk_cv_md(raw_cv_md: str, profile_id: uuid.UUID, tenant_id: uuid.UUID) -> list[dict]:
    chunks: list[dict] = []

    section_pattern = re.compile(r"^## (.+)$", re.MULTILINE)
    section_starts = [m.end() for m in section_pattern.finditer(raw_cv_md)]
    section_names = [m.group(1).strip() for m in section_pattern.finditer(raw_cv_md)]

    if not section_starts:
        chunks.append(
            {
                "source_type": "profile",
                "source_label": "Full CV",
                "content": raw_cv_md.strip(),
                "metadata_json": {"section": "full", "tags": ["cv"]},
            }
        )
        return chunks

    boundaries = [raw_cv_md.index(m.group()) for m in section_pattern.finditer(raw_cv_md)]
    boundaries.append(len(raw_cv_md))

    for i, name in enumerate(section_names):
        start = boundaries[i]
        end = boundaries[i + 1]
        section_text = raw_cv_md[start:end].strip()

        sub_pattern = re.compile(r"^(?:###\s*|-\s*|\d+\.\s*)(.+)$", re.MULTILINE)
        sub_starts = [m.start() for m in sub_pattern.finditer(section_text)]
        sub_names = [m.group(1).strip() for m in sub_pattern.finditer(section_text)]

        if not sub_starts:
            chunks.append(
                {
                    "source_type": "profile",
                    "source_label": name,
                    "content": section_text,
                    "metadata_json": {"section": name, "tags": [name.lower()]},
                }
            )
        else:
            sub_boundaries = sub_starts + [len(section_text)]
            for j, sub_name in enumerate(sub_names):
                sub_start = sub_boundaries[j]
                sub_end = sub_boundaries[j + 1]
                sub_content = section_text[sub_start:sub_end].strip()
                chunks.append(
                    {
                        "source_type": "profile",
                        "source_label": f"{name} / {sub_name}",
                        "content": sub_content,
                        "metadata_json": {
                            "section": name,
                            "sub_section": sub_name,
                            "tags": [name.lower(), sub_name.lower()],
                        },
                    }
                )

    return chunks


async def retrieve_evidence_for_job(
    db: AsyncSession, tenant_id: uuid.UUID, profile_id: uuid.UUID, parsed_job: dict
) -> list[EvidenceChunk]:
    result = await db.execute(
        select(EvidenceChunk).where(
            EvidenceChunk.tenant_id == tenant_id,
            EvidenceChunk.profile_id == profile_id,
        )
    )
    chunks: list[EvidenceChunk] = list(result.scalars().all())

    terms: set[str] = set()
    for val in parsed_job.values():
        if isinstance(val, str):
            for token in re.split(r"[\s,;./]+", val):
                t = token.strip().lower()
                if len(t) > 2:
                    terms.add(t)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    for token in re.split(r"[\s,;./]+", item):
                        t = token.strip().lower()
                        if len(t) > 2:
                            terms.add(t)

    scored: list[tuple[int, EvidenceChunk]] = []
    for chunk in chunks:
        content_lower = chunk.content.lower()
        score = sum(1 for term in terms if term in content_lower)
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:10]]


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

    evidence_result = await db.execute(
        select(EvidenceChunk).where(
            EvidenceChunk.tenant_id == tenant.id,
            EvidenceChunk.profile_id == profile.id,
        )
    )
    all_chunks: list[EvidenceChunk] = list(evidence_result.scalars().all())

    parsed_job = job.parsed_json or {"title": job.title, "company": job.company, "raw": job.raw_jd}
    relevant = await retrieve_evidence_for_job(db, tenant.id, profile.id, parsed_job)
    evidence_for_resume = relevant if relevant else all_chunks

    html: str | None = None
    provenance: dict[str, Any] = {"method": "template", "job_id": str(job_id)}

    try:
        gateway = LLMGateway()
        messages = _build_llm_prompt(profile, evidence_for_resume, parsed_job)
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
        html, prov = _generate_html_resume(profile, evidence_for_resume, parsed_job)
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
    evidence_chunks: list[EvidenceChunk],
    parsed_job: dict,
) -> list[dict]:
    evidence_text = "\n\n".join(f"[{c.source_label}]\n{c.content}" for c in evidence_chunks)
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
        f"Evidence chunks:\n{evidence_text}"
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def _generate_html_resume(
    profile: CandidateProfile,
    evidence_chunks: list[EvidenceChunk],
    parsed_job: dict,
) -> tuple[str, list[dict]]:
    job_title = (
        parsed_job.get("title", profile.headline)
        if isinstance(parsed_job, dict)
        else profile.headline
    )
    company = parsed_job.get("company", "") if isinstance(parsed_job, dict) else ""

    summary_parts: list[str] = []
    skills: list[str] = []
    experience_items: list[str] = []
    education_items: list[str] = []

    for c in evidence_chunks:
        section = (c.metadata_json or {}).get("section", "").lower() if c.metadata_json else ""
        label = c.source_label.lower()

        if "summary" in label or "profil" in section or "zusammenfassung" in section:
            summary_parts.append(c.content)
        elif "skill" in label or "qualifikation" in section or "kompetenz" in section:
            skills.append(c.content)
        elif (
            "education" in label
            or "ausbildung" in section
            or "bildung" in section
            or "studium" in section
        ):
            education_items.append(c.content)
        elif (
            "experience" in label
            or "erfahrung" in section
            or "berufserfahrung" in section
            or "career" in label
        ):
            experience_items.append(c.content)
        else:
            if not summary_parts:
                summary_parts.append(c.content)
            else:
                experience_items.append(c.content)

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

    provenance = [
        {
            "source": c.source_label,
            "section": (c.metadata_json or {}).get("section", "") if c.metadata_json else "",
        }
        for c in evidence_chunks
    ]
    return html, provenance


def _html_to_pdf(html: str) -> bytes:
    from weasyprint import HTML

    return HTML(string=html).write_pdf()
