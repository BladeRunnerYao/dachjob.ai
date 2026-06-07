import json
import logging
from typing import Any

from app.core.auth import TenantContext
from app.modules.matching.parser.skills import _enrich_parsed_skills

PROMPT_VERSION = "1.1"
REASONING_RETRY_PROMPT_VERSION = "1.1-reasoning-retry"


def jd_extract_messages(job: Any) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": "You are a job parser. Extract structured information from the job posting below. Return valid JSON only.",
        },
        {
            "role": "user",
            "content": (
                f"Title: {job.title}\n"
                f"Company: {job.company}\n"
                f"Location: {job.location or 'N/A'}\n"
                f"Description:\n{job.raw_jd}\n\n"
                "Extract JSON with these fields:\n"
                "title, company, location, work_model (remote/hybrid/onsite), "
                "language_requirements (list), must_have_skills (list), "
                "nice_to_have_skills (list), "
                "responsibilities (list of strings — extract each responsibility as a separate sentence), "
                "required_qualifications (list of strings — extract each required qualification as a separate sentence), "
                "preferred_qualifications (list of strings — extract each preferred/nice-to-have qualification as a separate sentence), "
                "salary_range (string or null), seniority (string or null), "
                "work_authorization (object or null with status, label, detail, evidence), "
                "dach_signals (object with location/country/language/work_authorization keys)\n\n"
                "Responsibility and qualification extraction rules:\n"
                "- Extract the full text of each responsibility or qualification as a separate string in the list — do not summarize or truncate.\n"
                "- Include the complete sentence or bullet point, preserving the original wording.\n"
                "- Responsibilities come from sections like 'Responsibilities', 'Your Responsibilities', 'What You'll Do', 'Your Tasks'.\n"
                "- Required qualifications come from sections like 'Requirements', 'Qualifications', 'Must Have', 'Your Profile', 'What We Look For'.\n"
                "- Preferred qualifications come from sections like 'Nice to Have', 'Preferred Qualifications', 'Bonus', 'Extras'.\n"
                "- If no explicit separation between required and preferred qualifications exists, put all qualification items in required_qualifications.\n\n"
                "Skill extraction rules:\n"
                "- Extract as many explicit atomic skills/capabilities as the posting contains, not only broad summary sentences.\n"
                "- Include programming languages, frameworks, databases, protocols, cloud services, infrastructure practices, security controls, testing/release practices, domain capabilities, collaboration requirements, and operational responsibilities.\n"
                "- Split combined requirements into separate items. Example: 'GCP infrastructure (Cloud Run, networking, IAM, TLS, firewall rules)' becomes "
                "['GCP', 'Cloud Run', 'Networking', 'IAM', 'TLS', 'Firewall rules'].\n"
                "- Treat capabilities like RBAC, job queues, CI/CD pipelines, GitHub Actions, E2E tests, QA, rollbacks, on-call, incident response, observability, monitoring, vulnerability scanning, penetration testing, and infrastructure hardening as skills when present.\n"
                "- Put skills from sections like 'Requirements', 'Your toolkit', 'What you must have', or equivalent in must_have_skills.\n"
                "- Put skills from sections like 'Nice to have', 'Preferred', 'Bonus', 'Extras that give you an edge', or equivalent in nice_to_have_skills.\n"
                "- Do not include skills that are mentioned only in a negated section such as 'What this role is NOT'.\n"
                "- Do NOT extract city names, office locations, or company headquarters as skills (e.g. Stockholm, London, New York). These are locations, not skills.\n"
                "- Put explicit 'must have' requirements in must_have_skills and optional/preferred items in nice_to_have_skills.\n"
                "- For Swiss jobs, flag explicit citizenship, work permit, EU/EFTA, right-to-work, or visa sponsorship restrictions in work_authorization with the exact evidence sentence."
            ),
        },
    ]


def needs_reasoning_parse_retry(parsed_json: dict[str, Any], job: Any) -> bool:
    raw_jd = job.raw_jd or ""
    skill_count = len(parsed_json.get("must_have_skills") or []) + len(
        parsed_json.get("nice_to_have_skills") or []
    )
    has_requirement_signal = any(
        signal in raw_jd.lower()
        for signal in (
            "requirements",
            "your toolkit",
            "what you must have",
            "must have",
            "qualifications",
            "your mission",
        )
    )
    return len(raw_jd) > 1200 and has_requirement_signal and skill_count < 4


async def parse_with_llm(
    tenant: TenantContext,
    job: Any,
    logger: logging.Logger,
    preferred_provider: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    from app.modules.llm_gateway.gateway import LLMGateway

    gateway = LLMGateway(preferred_provider=preferred_provider)
    messages = jd_extract_messages(job)
    content = await gateway.run_text(
        tenant_id=tenant.id,
        task="jd_extract",
        prompt_version=PROMPT_VERSION,
        model_tier="quality",
        messages=messages,
        response_format={"type": "json_object"},
    )
    if not content:
        return None, gateway.last_provider

    parsed_json = _enrich_parsed_skills(json.loads(content), job)
    if needs_reasoning_parse_retry(parsed_json, job):
        try:
            retry_content = await gateway.run_text(
                tenant_id=tenant.id,
                task="jd_extract",
                prompt_version=REASONING_RETRY_PROMPT_VERSION,
                messages=messages,
                reasoning=True,
                response_format={"type": "json_object"},
            )
            if retry_content:
                retry_json = _enrich_parsed_skills(json.loads(retry_content), job)
                if len(retry_json.get("skills") or []) > len(parsed_json.get("skills") or []):
                    parsed_json = retry_json
        except Exception:
            logger.exception("Reasoning model JD parse retry failed, keeping fast parse")

    return parsed_json, gateway.last_provider
