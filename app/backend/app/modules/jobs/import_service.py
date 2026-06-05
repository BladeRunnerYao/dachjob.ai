import logging
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantContext
from app.db.models import JobPosting
from app.modules.jobs.extractor import ScrapedJob
from app.modules.jobs.location_country import infer_countries_from_location, serialize_countries
from app.modules.jobs.repository import create_job, get_job
from app.modules.jobs.source_parsers import scrape_job_url
from app.modules.matching.service import parse_job_posting

logger = logging.getLogger(__name__)


async def _parse_imported_job(
    db: AsyncSession,
    tenant: TenantContext,
    job: JobPosting,
    *,
    force: bool,
) -> None:
    try:
        await parse_job_posting(db, tenant, job, force=force)
    except Exception:
        logger.warning("Failed to parse imported job %s", job.id, exc_info=True)


async def _upsert_scraped_job(
    db: AsyncSession,
    tenant: TenantContext,
    scraped: ScrapedJob,
) -> JobPosting:
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
        job.countries = serialize_countries(infer_countries_from_location(scraped.location))
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
        await _parse_imported_job(db, tenant, job, force=False)
        return job

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
    await _parse_imported_job(db, tenant, job, force=True)
    return job


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
        imported.append(await _upsert_scraped_job(db, tenant, scraped))

    refreshed_jobs: list[JobPosting] = []
    for job in imported:
        refreshed = await get_job(db, job.id)
        if refreshed:
            refreshed_jobs.append(refreshed)
    return refreshed_jobs, errors
