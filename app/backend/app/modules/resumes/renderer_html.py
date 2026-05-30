import re
from typing import Any

from app.db.models import CandidateProfile


def render_resume_html(
    profile: CandidateProfile,
    parsed_job: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
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

    return html, {}
