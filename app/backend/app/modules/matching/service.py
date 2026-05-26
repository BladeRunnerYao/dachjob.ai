import logging
import re

from app.core.auth import TenantContext
from app.modules.matching.jd_parser import parse_job_posting
from app.modules.matching.match_scorer import compute_match

__all__ = ["parse_job_posting", "compute_match", "format_raw_jd"]


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        cleaned = str(item).strip()
        if not cleaned:
            continue
        key = re.sub(r"\s+", " ", cleaned).strip(" .;:").casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


async def format_raw_jd(
    tenant: TenantContext,
    raw_text: str,
    title: str,
    company: str,
) -> str | None:
    if not raw_text or len(raw_text.strip()) < 100:
        return None

    from app.modules.llm_gateway.gateway import LLMGateway

    logger = logging.getLogger(__name__)
    gateway = LLMGateway()
    try:
        content = await gateway.run_text(
            tenant_id=tenant.id,
            task="jd_format",
            prompt_version="1.0",
            model_tier="fast",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a job description formatter. Reformat the raw job posting text "
                        "into clean, well-structured Markdown. CRITICAL RULES:\n"
                        "- PRESERVE ALL original content. Do NOT summarize, paraphrase, shorten, or omit any information.\n"
                        "- Do NOT add any facts, opinions, skills, requirements, or commentary that are not explicitly in the original text.\n"
                        "- Only improve the FORMATTING: add appropriate ## and ### headings (e.g. ## About the Role, ## Responsibilities, "
                        "## Requirements, ## Benefits, ## About the Company), convert lists to bullet points (- ), and add paragraph breaks.\n"
                        "- Remove obvious boilerplate, cookie consent notices, login prompts, navigation text, and page chrome that are not part of the job description.\n"
                        "- Keep the original language and wording. Do not translate, rewrite sentences, or change tone.\n"
                        "- Output ONLY the formatted Markdown. No preamble, no postamble, no explanations."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Job Title: {title}\n"
                        f"Company: {company}\n\n"
                        f"RAW TEXT TO FORMAT:\n{raw_text[:15000]}"
                    ),
                },
            ],
        )
        if content and len(content.strip()) > 80:
            return content.strip()
    except Exception:
        logger.exception("LLM JD formatting failed, keeping original raw_jd")

    return None
