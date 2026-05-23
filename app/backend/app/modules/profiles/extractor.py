import html
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


def _extract_h1(html_text: str) -> str | None:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, re.IGNORECASE | re.DOTALL)
    if match:
        content = re.sub(r"<[^>]+>", "", match.group(1))
        content = html.unescape(content).strip()
        return content
    return None


_CITIES = [
    "Stuttgart", "Berlin", "Munich", "München", "Hamburg", "Cologne", "Köln",
    "Frankfurt", "Düsseldorf", "Leipzig", "Dresden", "Nuremberg", "Nürnberg",
    "Hannover", "Bremen", "Bonn", "Mannheim", "Karlsruhe", "Augsburg",
    "Wiesbaden", "Münster", "Aachen", "Braunschweig", "Kiel", "Potsdam",
    "Zurich", "Zürich", "Vienna", "Wien", "Amsterdam", "Paris", "London",
]


_COUNTRIES = ["Germany", "Deutschland", "Switzerland", "Schweiz", "Austria", "Österreich"]


def _extract_location(text: str) -> str | None:
    for pattern in [
        r"\bBased\s+in\s*[:\s]+([^,\n]+(?:,\s*[^,\n]+)?)",
        r"\bLocation[:\s]+([^,\n]+(?:,\s*[^,\n]+)?)",
        r"[📍📌]\s*([^,\n]+(?:,\s*[^,\n]+)?)",
    ]:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            loc = match.group(1).strip()
            if loc:
                return loc
    for city in _CITIES:
        for country in _COUNTRIES:
            pair = re.search(
                rf"{re.escape(city)}\s*,\s*{re.escape(country)}",
                text, re.IGNORECASE,
            )
            if pair:
                return pair.group(0)
    for city in _CITIES:
        idx = text.find(city)
        if idx >= 0:
            nearby = text[max(0, idx - 40) : idx + 80]
            for country in _COUNTRIES:
                if country in nearby:
                    return f"{city}, {country}"
            return city
    return None


async def fetch_url_content(url: str) -> tuple[str, dict]:
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

    metadata: dict[str, str] = {}
    h1 = _extract_h1(html_text)
    if h1 and "|" in h1:
        parts = h1.split("|", 1)
        metadata["name"] = parts[0].strip()
        metadata["headline"] = parts[1].strip()
    location = _extract_location(text)
    if location:
        metadata["location"] = location

    return text[:30000], metadata


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
