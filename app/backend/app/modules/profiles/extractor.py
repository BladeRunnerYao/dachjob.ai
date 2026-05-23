import re
import io
from uuid import UUID

import httpx
from pypdf import PdfReader

from app.modules.llm_gateway.gateway import LLMGateway

def _strip_html(html_text: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", html_text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


async def fetch_url_content(url: str) -> str:
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=20.0,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
            )
        },
    ) as client:
        response = await client.get(url)
        response.raise_for_status()

    html_text = response.text
    text = _strip_html(html_text)

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    text = "\n".join(lines)

    return text[:30000]


def extract_pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n\n".join(pages)[:30000]


async def convert_to_cv_markdown(
    raw_text: str,
    source_label: str,
    tenant_id: UUID,
) -> str:
    system_prompt = (
        "You are a CV/resume extraction agent. Given raw text extracted from a personal website, "
        "LinkedIn profile, or PDF resume, extract all relevant information and format it into a "
        "clean, structured Markdown CV.\n\n"
        "Extract and organize the following sections:\n\n"
        "# Full Name\n\n"
        "## Profile / Summary\n"
        "Brief professional summary (2-3 sentences)\n\n"
        "## Experience\n"
        "For each position: **Job Title \u2014 Company (Start Date \u2013 End Date)**\n"
        "- Bullet points describing responsibilities and achievements\n"
        "Preserve all factual details, dates, company names, and metrics\n\n"
        "## Skills\n"
        "Comma-separated list of technical and professional skills, grouped by category if possible\n\n"
        "## Education\n"
        "For each degree: **Degree \u2014 Institution (Year)**\n"
        "- Field of study, notable achievements\n\n"
        "## Certifications (if any)\n"
        "- Certification name, issuing body, year\n\n"
        "## Languages (if any)\n"
        "- Language \u2014 Proficiency level\n\n"
        "Preserve ALL original information. Do NOT invent or fabricate any details. "
        "If the source text lacks information for a section, omit that section entirely.\n\n"
        "Output ONLY the Markdown content \u2014 no additional commentary, no JSON wrapper, no code fences."
    )

    gateway = LLMGateway()
    result = await gateway.run_text(
        tenant_id=tenant_id,
        task="profile_extract",
        prompt_version="1.0",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Raw text to extract from ({source_label}):\n\n{raw_text}"},
        ],
    )

    return result.strip()
