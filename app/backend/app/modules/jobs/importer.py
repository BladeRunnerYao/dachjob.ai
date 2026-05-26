import html
import re
from datetime import datetime
from urllib.parse import parse_qs, urlparse
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantContext
from app.db.models import JobPosting
from app.modules.jobs.extractor import (
    ScrapedJob,
    _find_job_posting_jsonld,
    _location_from_jsonld,
    _meta,
    _normalize_text,
    _page_title,
    _parse_datetime,
    _salary_from_jsonld,
    _strip_html,
)
from app.modules.jobs.fetcher import (
    DEFAULT_JOB_REQUEST_HEADERS,
    _fetch_greenhouse_board_name,
    _fetch_job_page,
)
from app.modules.jobs.repository import create_job, get_job
from app.modules.matching.service import parse_job_posting


def _extract_company_from_title(title: str, hostname: str) -> tuple[str, str]:
    cleaned = re.sub(r"\s*\|\s*LinkedIn\s*$", "", title, flags=re.IGNORECASE).strip()
    jobs_at_match = re.match(r"(.+?)\s+\|\s+Jobs at\s+(.+)$", cleaned, re.IGNORECASE)
    if jobs_at_match:
        return jobs_at_match.group(1).strip(), jobs_at_match.group(2).strip()
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
        start_markers = [
            "About You",
            "Mission",
            "The Impact You Will Have",
            "Tasks",
            "Responsibilities",
            "Report this job",
        ]
        for marker in start_markers:
            index = cleaned.find(marker)
            if index >= 0:
                cleaned = cleaned[index + len(marker) :]
                break
        end_markers = [
            "Referrals increase your chances",
            "Similar jobs",
            "People also viewed",
            "Explore top content",
            "LinkedIn ©",
        ]
        earliest_index = None
        for marker in end_markers:
            index = cleaned.find(marker)
            if index >= 0 and (earliest_index is None or index < earliest_index):
                earliest_index = index
        if earliest_index is not None:
            cleaned = cleaned[:earliest_index]
    return _normalize_text(cleaned)


def _linkedin_description_from_html(html_text: str) -> str | None:
    patterns = (
        r'<div[^>]+class=["\'][^"\']*\bshow-more-less-html__markup\b[^"\']*["\'][^>]*>(.*?)</div>',
        r'<div[^>]+class=["\'][^"\']*\bdescription__text\b[^"\']*["\'][^>]*>(.*?)</div>',
    )
    for pattern in patterns:
        match = re.search(pattern, html_text, re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        description = _strip_html(match.group(1))
        if len(description) >= 80:
            return description
    return None


def _bmwgroup_description_from_html(html_text: str) -> str | None:
    description_match = re.search(
        r'<div[^>]+class=["\'][^"\']*\bcmp-text\b[^"\']*["\'][^>]+itemprop=["\']description["\'][^>]*>(.*?)</div>',
        html_text,
        re.IGNORECASE | re.DOTALL,
    )
    if not description_match:
        return None

    parts: list[str] = []
    intro_match = re.search(
        r'<div[^>]+class=["\'][^"\']*\bgrp-jobdescription__content\b[^"\']*\btext\b[^"\']*["\'][^>]*>.*?'
        r'<div[^>]+class=["\'][^"\']*\bcmp-text\b[^"\']*["\'][^>]*>(.*?)</div>\s*'
        r'<div[^>]+class=["\'][^"\']*\bcmp-text\b[^"\']*["\'][^>]+itemprop=["\']description["\']',
        html_text,
        re.IGNORECASE | re.DOTALL,
    )
    if intro_match:
        intro = _strip_html(intro_match.group(1))
        if intro:
            parts.append(intro)

    description = _strip_html(description_match.group(1))
    if description:
        parts.append(description)

    result = _normalize_text("\n\n".join(parts))
    return result if len(result) >= 80 else None


def _bmwgroup_labeled_item(html_text: str, class_name: str) -> str | None:
    pattern = (
        rf'<div[^>]+class=["\'][^"\']*\b{re.escape(class_name)}\b[^"\']*["\'][^>]*>(.*?)</div>'
    )
    match = re.search(pattern, html_text, re.IGNORECASE | re.DOTALL)
    return _strip_html(match.group(1)) if match else None


def _bmwgroup_location_from_html(html_text: str) -> str | None:
    location = _bmwgroup_labeled_item(html_text, "grp-jobdescription__jobLocation")
    if location:
        return location
    locality_match = re.search(
        r'<div[^>]+itemprop=["\']addressLocality["\'][^>]*>(.*?)</div>',
        html_text,
        re.IGNORECASE | re.DOTALL,
    )
    region_match = re.search(
        r'<div[^>]+itemprop=["\']addressRegion["\'][^>]*>(.*?)</div>',
        html_text,
        re.IGNORECASE | re.DOTALL,
    )
    parts = [_strip_html(match.group(1)) for match in (locality_match, region_match) if match]
    return ", ".join(part for part in parts if part) or None


def _bmwgroup_company_from_html(html_text: str) -> str | None:
    legal_entity = _bmwgroup_labeled_item(html_text, "grp-jobdescription__jobLegalEntity")
    if legal_entity:
        return legal_entity
    organization_match = re.search(
        r'itemprop=["\']hiringOrganization["\'][\s\S]+?itemprop=["\']name["\'][^>]*>(.*?)</div>',
        html_text,
        re.IGNORECASE,
    )
    return _strip_html(organization_match.group(1)) if organization_match else None


def _bmwgroup_employment_type_from_html(html_text: str) -> str | None:
    matches = re.findall(
        r'<div[^>]+itemprop=["\']employmentType["\'][^>]*>(.*?)</div>',
        html_text,
        re.IGNORECASE | re.DOTALL,
    )
    for match in reversed(matches):
        value = _strip_html(match)
        if value and "@" not in value:
            return value
    return None


def _bmwgroup_posted_at_from_html(html_text: str) -> datetime | None:
    match = re.search(
        r'<div[^>]+itemprop=["\']datePosted["\'][^>]*>(\d{8})</div>', html_text, re.IGNORECASE
    )
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d")
    except ValueError:
        return None


def _extract_labeled_value(text: str, label: str) -> str | None:
    pattern = rf"{re.escape(label)}\s*[:\n]?\s*([^\n]+)"
    match = re.search(pattern, text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _source_job_id(url: str) -> str | None:
    parsed = urlparse(url)
    if "linkedin." in parsed.netloc:
        match = re.search(r"/jobs/view/(\d+)", parsed.path)
        return match.group(1) if match else None
    query = parse_qs(parsed.query)
    for key in ("gh_jid", "jobId", "job_id", "jobid"):
        query_id = query.get(key)
        if query_id and query_id[0].isdigit():
            return query_id[0]
    digits = re.findall(r"\d{5,}", parsed.path)
    return digits[-1] if digits else None


GREENHOUSE_BOARD_BY_HOST = {
    "getyourguide.careers": "getyourguide",
    "helsing.ai": "helsing",
    "n26.com": "n26",
    "sumup.com": "sumup",
    "traderepublic.com": "traderepublicbank",
    "wayve.firststage.co": "wayve",
}


def _greenhouse_board_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    host = parsed.netloc.removeprefix("www.")
    path_parts = [part for part in parsed.path.split("/") if part]
    query = parse_qs(parsed.query)
    board = query.get("for")
    if host in {"boards.greenhouse.io", "job-boards.greenhouse.io"} and board:
        return board[0]
    if host in {"boards.greenhouse.io", "job-boards.greenhouse.io"} and path_parts:
        return path_parts[0]
    return None


def _greenhouse_board_from_known_host(url: str) -> str | None:
    host = urlparse(url).netloc.removeprefix("www.")
    return GREENHOUSE_BOARD_BY_HOST.get(host)


def _greenhouse_job_id_from_url_or_html(url: str, html_text: str) -> str | None:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for key in ("gh_jid", "jobId", "job_id", "jobid", "token"):
        values = query.get(key)
        if values and re.fullmatch(r"\d{5,}", values[0]):
            return values[0]
    digits = re.findall(r"\d{5,}", parsed.path)
    if digits:
        return digits[-1]
    for pattern in (
        r'<meta[^>]+name=["\']api_id["\'][^>]+content=["\'](\d{5,})["\']',
        r'<meta[^>]+content=["\'](\d{5,})["\'][^>]+name=["\']api_id["\']',
        r"\bjobId\s*=\s*['\"](\d{5,})['\"]",
    ):
        match = re.search(pattern, html_text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _greenhouse_board_from_html(html_text: str) -> str | None:
    patterns = (
        r"boards-api\.greenhouse\.io/v1/boards/([^/\"'`]+)/jobs",
        r"boards\.greenhouse\.io/embed/job_app\?for=([^&\"']+)",
    )
    for pattern in patterns:
        match = re.search(pattern, html_text, re.IGNORECASE)
        if match:
            return html.unescape(match.group(1)).strip()
    return None


def _greenhouse_company_from_board(board: str) -> str:
    words = re.split(r"[-_]+", board)
    return " ".join(word.capitalize() for word in words if word) or board


async def _scrape_greenhouse_job(
    client: httpx.AsyncClient,
    requested_url: str,
    final_url: str,
    hostname: str,
    html_text: str,
) -> ScrapedJob | None:
    direct_or_known_board = (
        _greenhouse_board_from_url(final_url)
        or _greenhouse_board_from_known_host(requested_url)
        or _greenhouse_board_from_known_host(final_url)
    )
    board = direct_or_known_board or _greenhouse_board_from_html(html_text)
    job_id = _greenhouse_job_id_from_url_or_html(
        final_url, html_text
    ) or _greenhouse_job_id_from_url_or_html(requested_url, html_text)
    if not board or not job_id:
        return None

    api_url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"
    response = await client.get(api_url)
    if response.status_code == 404:
        if direct_or_known_board:
            raise ValueError("Greenhouse job not found")
        return None
    response.raise_for_status()
    data = response.json()
    content = _strip_html(data.get("content"))
    if len(content) < 40:
        return None

    meta_title = _meta(html_text, "og:title") or _page_title(html_text) or ""
    title = _normalize_text(data.get("title")) or meta_title or "Imported Job"
    _title_from_page, company_from_page = _extract_company_from_title(meta_title or title, hostname)
    company = await _fetch_greenhouse_board_name(client, board)
    if not company and company_from_page and company_from_page != hostname:
        company = re.sub(r"^Jobs at\s+", "", company_from_page, flags=re.IGNORECASE).strip()
    company = company or _greenhouse_company_from_board(board)

    location = None
    api_location = data.get("location")
    if isinstance(api_location, dict):
        location = _normalize_text(api_location.get("name"))

    departments = data.get("departments") if isinstance(data.get("departments"), list) else []
    offices = data.get("offices") if isinstance(data.get("offices"), list) else []
    scraped_json = {
        "final_url": final_url,
        "source_hostname": hostname,
        "ats_provider": "greenhouse",
        "greenhouse_board": board,
        "greenhouse_job_id": job_id,
        "greenhouse_api_url": api_url,
        "greenhouse_content_length": len(data.get("content") or ""),
        "json_ld_found": False,
        "meta_title": _meta(html_text, "og:title"),
        "meta_description": _meta(html_text, "description", "og:description"),
        "departments": departments,
        "offices": offices,
    }

    return ScrapedJob(
        title=title[:500],
        company=company[:500],
        url=final_url,
        location=location,
        raw_jd=content[:20000],
        source=hostname,
        source_job_id=job_id,
        posted_at=None,
        employment_type=None,
        workplace=None,
        salary_text=None,
        scraped_json=scraped_json,
    )


def _looks_like_non_job_page(hostname: str, final_url: str, title: str | None) -> bool:
    title_lower = (title or "").casefold()
    path = urlparse(final_url).path.casefold()
    if hostname in {"boards.greenhouse.io", "job-boards.greenhouse.io"} and "confirmation" in path:
        return True
    if hostname.endswith("google.com") and title_lower == "jobs search — google careers":
        return True
    if "linkedin." in hostname and re.search(
        r"^\s*\d+[.,]?\d*\s+(?:jobs?\s+(?:in|for|für)\b|.+\s+jobs?\s+(?:in|for|für)\b)",
        title_lower,
    ):
        return True
    return False


async def scrape_job_url(url: str) -> ScrapedJob:
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=20.0,
    ) as client:
        response, fetch_profile = await _fetch_job_page(client, url)
        response.raise_for_status()

        html_text = response.text
        final_url = str(response.url)
        parsed_url = urlparse(final_url)
        hostname = parsed_url.netloc.removeprefix("www.")

        greenhouse_job = await _scrape_greenhouse_job(client, url, final_url, hostname, html_text)
        if greenhouse_job:
            return greenhouse_job

    job_json = _find_job_posting_jsonld(html_text) or {}

    meta_title = _meta(html_text, "og:title")
    title = _normalize_text(job_json.get("title")) or meta_title or _page_title(html_text)
    title = title or "Imported Job"
    if _looks_like_non_job_page(hostname, final_url, title):
        raise ValueError("No job description content found on page")

    organization = job_json.get("hiringOrganization")
    company = None
    if isinstance(organization, dict):
        company = _normalize_text(organization.get("name"))
    if not company and "bmwgroup.jobs" in hostname:
        company = _bmwgroup_company_from_html(html_text)
    if not company:
        title, company = _extract_company_from_title(title, hostname)

    meta_description = _meta(html_text, "description", "og:description") or ""
    description = _strip_html(job_json.get("description")) if job_json else ""
    if not description and "bmwgroup.jobs" in hostname:
        description = _bmwgroup_description_from_html(html_text) or ""
    if not description and "linkedin." in hostname:
        description = _linkedin_description_from_html(html_text) or ""
        if not description:
            raise ValueError("No LinkedIn job description content found on page")
    if not description:
        body_description = _clean_source_text(hostname, _strip_html(html_text))
        description = max([meta_description, body_description], key=len)
    if not job_json and len((description or "").strip()) < 80:
        raise ValueError("No job description content found on page")

    location = (
        _location_from_jsonld(job_json)
        or (_bmwgroup_location_from_html(html_text) if "bmwgroup.jobs" in hostname else None)
        or _meta(html_text, "job:location", "og:locality")
        or _location_from_title(meta_title)
    )
    employment_type = job_json.get("employmentType")
    if isinstance(employment_type, list):
        employment_type = ", ".join(str(item) for item in employment_type)
    if not employment_type and "bmwgroup.jobs" in hostname:
        employment_type = _bmwgroup_employment_type_from_html(html_text)
    if not employment_type:
        employment_type = _extract_labeled_value(description, "Employment type")

    workplace = job_json.get("jobLocationType") if job_json else None
    if not workplace:
        location_line = _extract_labeled_value(description, "Location") or _extract_labeled_value(
            meta_description, "Location"
        )
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
        "fetch_profile": fetch_profile,
    }

    return ScrapedJob(
        title=title[:500],
        company=(company or hostname or "Unknown")[:500],
        url=final_url,
        location=location,
        raw_jd=(description or title)[:20000],
        source=hostname,
        source_job_id=_source_job_id(final_url),
        posted_at=(
            _parse_datetime(job_json.get("datePosted") if job_json else None)
            or (_bmwgroup_posted_at_from_html(html_text) if "bmwgroup.jobs" in hostname else None)
        ),
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
            errors.append(
                {"url": url, "error": f"HTTP {e.response.status_code}: could not fetch page"}
            )
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

        scraped.scraped_json["raw_text_original"] = scraped.raw_jd[:10000]
        scraped.scraped_json["raw_jd_preserved"] = True

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
            await db.flush()
            try:
                await parse_job_posting(db, tenant, job, force=False)
            except Exception:
                pass
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
