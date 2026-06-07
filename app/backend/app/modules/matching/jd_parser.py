import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantContext
from app.modules.jobs.repository import sync_job_skills
from app.modules.matching.parser import deterministic_parse, parse_with_llm
from app.modules.matching.parser.skills import _enrich_parsed_skills, _extract_listed_skills

__all__ = [
    "_enrich_parsed_skills",
    "_extract_listed_skills",
    "parse_job_posting",
]


async def parse_job_posting(
    db: AsyncSession,
    tenant: TenantContext,
    job: Any,
    force: bool = False,
    preferred_provider: str | None = None,
) -> dict[str, Any]:
    logger = logging.getLogger(__name__)

    if job.parsed_json and not force:
        await sync_job_skills(db, job, job.parsed_json, source="cached_parser")
        logger.info("parse_cache_hit | job_id=%s tenant_id=%s", job.id, tenant.id)
        try:
            from app.db.models import LLMRun

            run = LLMRun(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                task="jd_extract",
                provider="cache",
                model="cache",
                prompt_version="1.1",
                latency_ms=0,
                status="cache_hit",
            )
            db.add(run)
            await db.flush()
        except Exception:
            logger.warning("Failed to record cached JD parser run", exc_info=True)
        return {"status": job.status or "parsed", "parsed_json": job.parsed_json}

    try:
        parsed_json, source = await parse_with_llm(
            tenant, job, logger, preferred_provider=preferred_provider
        )
        if parsed_json:
            job.parsed_json = parsed_json
            job.status = "parsed"
            await sync_job_skills(db, job, parsed_json, source=source)
            await db.flush()
            return {"status": "parsed", "parsed_json": parsed_json}
    except Exception:
        logger.exception("LLM job parsing failed, falling back to deterministic parser")

    parsed_json = _enrich_parsed_skills(deterministic_parse(job), job)
    job.parsed_json = parsed_json
    job.status = "parsed"
    await sync_job_skills(db, job, parsed_json, source="deterministic_parser")
    await db.flush()
    return {"status": "parsed", "parsed_json": parsed_json}
