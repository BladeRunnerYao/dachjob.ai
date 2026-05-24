import html
import json
import re
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urlparse
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant import TenantContext
from app.db.models import JobPosting
from app.modules.jobs.repository import create_job, get_job
from app.modules.matching.service import parse_job_posting


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag in {"p", "li", "br", "div", "section", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if tag in {"p", "li", "div", "section"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            cleaned = data.strip()
            if cleaned:
                self.parts.append(cleaned)

    def text(self) -> str:
        return _normalize_text(" ".join(self.parts))


@dataclass
class ScrapedJob:
    title: str
    company: str
    url: str
    location: str | None
    raw_jd: str
    source: str | None
    source_job_id: str | None
    posted_at: datetime | None
    employment_type: str | None
    workplace: str | None
    salary_text: str | None
    scraped_json: dict


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    value = html.unescape(value)
    value = re.sub(r"\r\n?", "\n", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n\s*\n\s*", "\n\n", value)
    return value.strip()


def _strip_html(value: str | None) -> str:
    parser = _TextExtractor()
    parser.feed(value or "")
    return parser.text()


def _meta(html_text: str, *names: str) -> str | None:
    for name in names:
        patterns = [
            rf'<meta[^>]+(?:name|property)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']',
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:name|property)=["\']{re.escape(name)}["\']',
        ]
        for pattern in patterns:
            match = re.search(pattern, html_text, re.IGNORECASE | re.DOTALL)
            if match:
                return _normalize_text(match.group(1))
    return None


def _page_title(html_text: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
    return _normalize_text(match.group(1)) if match else None


def _json_ld_objects(html_text: str) -> list[dict]:
    objects: list[dict] = []
    scripts = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text,
        re.IGNORECASE | re.DOTALL,
    )
    for script in scripts:
        try:
            loaded = json.loads(html.unescape(script).strip())
        except json.JSONDecodeError:
            continue
        stack = loaded if isinstance(loaded, list) else [loaded]
        while stack:
            item = stack.pop(0)
            if not isinstance(item, dict):
                continue
            objects.append(item)
            graph = item.get("@graph")
            if isinstance(graph, list):
                stack.extend(graph)
    return objects


def _find_job_posting_jsonld(html_text: str) -> dict | None:
    for item in _json_ld_objects(html_text):
        item_type = item.get("@type")
        types = item_type if isinstance(item_type, list) else [item_type]
        if any(str(t).lower() == "jobposting" for t in types):
            return item
    return None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def _extract_company_from_title(title: str, hostname: str) -> tuple[str, str]:
    cleaned = re.sub(r"\s*\|\s*LinkedIn\s*$", "", title, flags=re.IGNORECASE).strip()
    linkedin_match = re.match(r"(.+?)\s+hiring\s+(.+?)(?:\s+in\s+.+)?$", cleaned, re.IGNORECASE)
    if linkedin_match:
        return linkedin_match.group(2).strip(), linkedin_match.group(1).strip()
    for pattern in (r"(.+?)\s+at\s+(.+)$", r"(.+?)\s+\|\s+(.+)$"):
        match = re.match(pattern, cleaned, re.IGNORECASE)
        if match:
            return match.group(1).strip(), match.group(2).strip()
    parts = [p.strip() for p in cleaned.rsplit(" - ", 1)]
    if len(parts) == 2 and parts[0] and parts[1]:
        return parts[0], parts[1]
    return cleaned or "Imported Job", hostname or "Unknown"


def _location_from_title(title: str | None) -> str | None:
    if not title:
        return None
    cleaned = re.sub(r"\s*\|\s*LinkedIn\s*$", "", title, flags=re.IGNORECASE).strip()
    match = re.search(r"\s+in\s+(.+)$", cleaned, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _clean_source_text(source: str, text: str) -> str:
    cleaned = text
    if "linkedin." in source:
        start_markers = ["About You", "Mission", "The Impact You Will Have", "Tasks", "Responsibilities", "Report this job"]
        for marker in start_markers:
            index = cleaned.find(marker)
            if index >= 0:
                cleaned = cleaned[index + len(marker):]
                break
        end_markers = [
            "Referrals increase your chances",
            "Similar jobs",
            "People also viewed",
            "Explore top content",
            "LinkedIn ©",
        ]
        for marker in end_markers:
            index = cleaned.find(marker)
            if index >= 0:
                cleaned = cleaned[:index]
                break
    return _normalize_text(cleaned)


def _extract_labeled_value(text: str, label: str) -> str | None:
    pattern = rf"{re.escape(label)}\s*[:\n]?\s*([^\n]+)"
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _source_job_id(url: str) -> str | None:
    parsed = urlparse(url)
    if "linkedin." in parsed.netloc:
        match = re.search(r"/jobs/view/(\d+)", parsed.path)
        return match.group(1) if match else None
    digits = re.findall(r"\d{5,}", parsed.path)
    return digits[-1] if digits else None


def _location_from_jsonld(job_json: dict) -> str | None:
    locations = job_json.get("jobLocation")
    if not locations:
        return None
    if isinstance(locations, dict):
        locations = [locations]
    parts: list[str] = []
    for item in locations if isinstance(locations, list) else []:
        address = item.get("address") if isinstance(item, dict) else None
        if not isinstance(address, dict):
            continue
        location_parts = [
            address.get("addressLocality"),
            address.get("addressRegion"),
            address.get("addressCountry"),
        ]
        location = ", ".join(str(p) for p in location_parts if p)
        if location:
            parts.append(location)
    return "; ".join(parts) if parts else None


def _salary_from_jsonld(job_json: dict) -> str | None:
    salary = job_json.get("baseSalary")
    if not isinstance(salary, dict):
        return None
    currency = salary.get("currency")
    value = salary.get("value")
    if isinstance(value, dict):
        min_value = value.get("minValue")
        max_value = value.get("maxValue")
        unit = value.get("unitText")
        if min_value and max_value:
            return " ".join(str(p) for p in (currency, f"{min_value}-{max_value}", unit) if p)
        if value.get("value"):
            return " ".join(str(p) for p in (currency, value.get("value"), unit) if p)
    return None


async def scrape_job_url(url: str) -> ScrapedJob:
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
    final_url = str(response.url)
    parsed_url = urlparse(final_url)
    hostname = parsed_url.netloc.removeprefix("www.")
    job_json = _find_job_posting_jsonld(html_text) or {}

    meta_title = _meta(html_text, "og:title")
    title = _normalize_text(job_json.get("title")) or meta_title or _page_title(html_text)
    title = title or "Imported Job"

    organization = job_json.get("hiringOrganization")
    company = None
    if isinstance(organization, dict):
        company = _normalize_text(organization.get("name"))
    if not company:
        title, company = _extract_company_from_title(title, hostname)

    meta_description = _meta(html_text, "description", "og:description") or ""
    description = _strip_html(job_json.get("description")) if job_json else ""
    if not description:
        body_description = _clean_source_text(hostname, _strip_html(html_text))
        description = max([meta_description, body_description], key=len)

    location = (
        _location_from_jsonld(job_json)
        or _meta(html_text, "job:location", "og:locality")
        or _location_from_title(meta_title)
    )
    employment_type = job_json.get("employmentType")
    if isinstance(employment_type, list):
        employment_type = ", ".join(str(item) for item in employment_type)
    if not employment_type:
        employment_type = _extract_labeled_value(description, "Employment type")

    workplace = job_json.get("jobLocationType") if job_json else None
    if not workplace:
        location_line = _extract_labeled_value(description, "Location") or _extract_labeled_value(meta_description, "Location")
        if location_line and "remote" in location_line.lower():
            workplace = "remote"
    if not workplace and ("remote" in description.lower() or "remote" in meta_description.lower()):
        workplace = "remote"

    scraped_json = {
        "final_url": final_url,
        "source_hostname": hostname,
        "json_ld_found": bool(job_json),
        "meta_title": _meta(html_text, "og:title"),
        "meta_description": _meta(html_text, "description", "og:description"),
    }

    return ScrapedJob(
        title=title[:500],
        company=(company or hostname or "Unknown")[:500],
        url=final_url,
        location=location,
        raw_jd=(description or title)[:20000],
        source=hostname,
        source_job_id=_source_job_id(final_url),
        posted_at=_parse_datetime(job_json.get("datePosted") if job_json else None),
        employment_type=str(employment_type) if employment_type else None,
        workplace=workplace,
        salary_text=_salary_from_jsonld(job_json),
        scraped_json=scraped_json,
    )


async def import_job_urls(
    db: AsyncSession,
    tenant: TenantContext,
    urls: list[str],
) -> tuple[list[JobPosting], list[dict[str, str]]]:
    imported: list[JobPosting] = []
    errors: list[dict[str, str]] = []
    cleaned_urls = [url.strip() for url in urls if url.strip()]
    for url in cleaned_urls:
        try:
            scraped = await scrape_job_url(url)
        except httpx.HTTPStatusError as e:
            errors.append({"url": url, "error": f"HTTP {e.response.status_code}: could not fetch page"})
            continue
        except httpx.TimeoutException:
            errors.append({"url": url, "error": "Request timed out after 20s"})
            continue
        except httpx.RequestError as e:
            errors.append({"url": url, "error": f"Network error: {str(e)[:200]}"})
            continue
        except Exception as e:
            errors.append({"url": url, "error": f"Scrape error: {str(e)[:200]}"})
            continue

        existing_result = await db.execute(
            select(JobPosting).where(
                JobPosting.tenant_id == tenant.id,
                JobPosting.url == scraped.url,
            )
        )
        job = existing_result.scalar_one_or_none()
        if job:
            job.title = scraped.title
            job.company = scraped.company
            job.location = scraped.location
            job.raw_jd = scraped.raw_jd
            job.source = scraped.source
            job.source_job_id = scraped.source_job_id
            job.posted_at = scraped.posted_at
            job.employment_type = scraped.employment_type
            job.workplace = scraped.workplace
            job.salary_text = scraped.salary_text
            job.scraped_json = scraped.scraped_json
            job.status = "imported"
            job.parsed_json = None
            await db.flush()
        else:
            job = await create_job(
                db=db,
                tenant_id=UUID(str(tenant.id)),
                title=scraped.title,
                company=scraped.company,
                raw_jd=scraped.raw_jd,
                url=scraped.url,
                location=scraped.location,
                source=scraped.source,
                source_job_id=scraped.source_job_id,
                posted_at=scraped.posted_at,
                employment_type=scraped.employment_type,
                workplace=scraped.workplace,
                salary_text=scraped.salary_text,
                scraped_json=scraped.scraped_json,
            )
            job.status = "imported"
            await db.flush()

        try:
            await parse_job_posting(db, tenant, job, force=True)
        except Exception:
            pass

        imported.append(job)

    refreshed_jobs: list[JobPosting] = []
    for job in imported:
        refreshed = await get_job(db, job.id)
        if refreshed:
            refreshed_jobs.append(refreshed)
    return refreshed_jobs, errors
