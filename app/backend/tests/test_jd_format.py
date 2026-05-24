"""
Tests for the JD formatting pipeline (format_raw_jd).

Run with:
    cd app/backend && source .venv/bin/activate && PYTHONPATH=. python3 -m pytest tests/test_jd_format.py -v
"""
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

RAW_JD_INPUT = """AI Engineer - FDE (Forward Deployed Engineer) (ALL LEVELS)Location: Germany - RemoteReq ID: CSQ327R197Recruiter: Dina HussainMissionThe AI Forward Deployed Engineering (AI FDE) team is a highly specialized customer-facing AI team at Databricks. We deliver professional services engagements to help our customers build and productionize first-of-its-kind AI applications.The Impact You Will HaveDevelop cutting-edge GenAI solutions, incorporating the latest techniques from Databricks AI research to solve customer problemsOwn production rollouts of consumer and internally facing GenAI applicationsWhat We Look ForExperience building GenAI applications, including RAG, multi-agent systems, Text2SQL, fine-tuning, etc., with tools such as HuggingFace, LangChain, and DSPyExpertise in deploying production-grade GenAI applications, including evaluation and optimizations Experience building production-grade machine learning deployments on AWS, Azure, or GCPAbout DatabricksDatabricks is the data and AI company. More than 10,000 organizations worldwide rely on the Databricks Data Intelligence Platform."""

FORMATTED_MOCK_OUTPUT = """## AI Engineer - FDE (Forward Deployed Engineer) \u2014 Databricks

**Location:** Germany - Remote
**Req ID:** CSQ327R197
**Recruiter:** Dina Hussain

### Mission
The AI Forward Deployed Engineering (AI FDE) team is a highly specialized customer-facing AI team at Databricks.

### The Impact You Will Have
- Develop cutting-edge GenAI solutions
- Own production rollouts

### What We Look For
- Experience building GenAI applications, including RAG, multi-agent systems
- Expertise in deploying production-grade GenAI applications
- Experience building production-grade machine learning deployments on AWS, Azure, or GCP

### About Databricks
Databricks is the data and AI company."""


def _make_mock_gateway():
    """Create a mock LLMGateway with the run_text method."""
    mock = MagicMock()
    mock.run_text = AsyncMock()
    return mock


class TestFormatRawJD:
    """Tests for format_raw_jd with mocked LLM gateway."""

    @pytest.mark.asyncio
    async def test_format_returns_none_for_short_text(self):
        from app.core.tenant import TenantContext
        from app.modules.matching.service import format_raw_jd

        tenant = TenantContext(slug="test", name="test")
        result = await format_raw_jd(tenant, "Short text", "Title", "Company")
        assert result is None

    @pytest.mark.asyncio
    async def test_format_preserves_key_content(self):
        from app.core.tenant import TenantContext
        from app.modules.matching.service import format_raw_jd

        tenant = TenantContext(slug="test", name="test")
        mock_gw = _make_mock_gateway()
        mock_gw.run_text.return_value = FORMATTED_MOCK_OUTPUT

        with patch("app.modules.llm_gateway.gateway.LLMGateway", return_value=mock_gw):
            result = await format_raw_jd(tenant, RAW_JD_INPUT, "AI Engineer", "Databricks")

        assert result is not None
        assert "Databricks" in result
        assert "### Mission" in result
        assert "### What We Look For" in result
        assert "### The Impact You Will Have" in result
        assert "### About Databricks" in result
        assert "RAG" in result
        assert "AWS" in result
        mock_gw.run_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_format_sends_correct_prompt(self):
        from app.core.tenant import TenantContext
        from app.modules.matching.service import format_raw_jd

        tenant = TenantContext(slug="test", name="test")
        mock_gw = _make_mock_gateway()
        mock_gw.run_text.return_value = FORMATTED_MOCK_OUTPUT

        with patch("app.modules.llm_gateway.gateway.LLMGateway", return_value=mock_gw):
            await format_raw_jd(tenant, RAW_JD_INPUT, "AI Engineer", "Databricks")

        call_kwargs = mock_gw.run_text.call_args.kwargs
        assert call_kwargs["task"] == "jd_format"
        assert call_kwargs["prompt_version"] == "1.0"

        messages = call_kwargs["messages"]
        assert len(messages) == 2

        system_msg = messages[0]["content"]
        assert "PRESERVE ALL original content" in system_msg
        assert "Do NOT summarize" in system_msg
        assert "Do NOT add any facts" in system_msg
        assert "Do not translate" in system_msg

        user_msg = messages[1]["content"]
        assert "AI Engineer" in user_msg
        assert "Databricks" in user_msg
        assert "RAW TEXT TO FORMAT" in user_msg

    @pytest.mark.asyncio
    async def test_format_fallback_on_error(self):
        from app.core.tenant import TenantContext
        from app.modules.matching.service import format_raw_jd

        tenant = TenantContext(slug="test", name="test")
        mock_gw = _make_mock_gateway()
        mock_gw.run_text.side_effect = RuntimeError("API error")

        with patch("app.modules.llm_gateway.gateway.LLMGateway", return_value=mock_gw):
            result = await format_raw_jd(tenant, RAW_JD_INPUT, "Title", "Company")

        assert result is None

    @pytest.mark.asyncio
    async def test_format_skips_empty_llm_response(self):
        from app.core.tenant import TenantContext
        from app.modules.matching.service import format_raw_jd

        tenant = TenantContext(slug="test", name="test")
        mock_gw = _make_mock_gateway()
        mock_gw.run_text.return_value = "  OK "

        with patch("app.modules.llm_gateway.gateway.LLMGateway", return_value=mock_gw):
            result = await format_raw_jd(tenant, RAW_JD_INPUT, "Title", "Company")

        assert result is None

    def test_raw_jd_input_preserves_all_sections(self):
        """Verify the mock input contains all sections from the real JD."""
        sections = [
            "AI Forward Deployed Engineering",
            "The Impact You Will Have",
            "What We Look For",
            "RAG",
            "LangChain",
            "DSPy",
            "HuggingFace",
            "AWS",
            "Azure",
            "GCP",
            "Databricks is the data and AI company",
        ]
        for section in sections:
            assert section in RAW_JD_INPUT, f"Missing: {section}"


class TestSystemPromptRules:
    """Verify the critical content-preservation rules in the system prompt."""

    def test_system_prompt_content_rules(self):
        from app.modules.matching.service import format_raw_jd as fn

        source = fn.__code__.co_consts
        prompt = None
        for const in source:
            if isinstance(const, str) and "PRESERVE ALL" in const:
                prompt = const
                break
        if prompt is None:
            pytest.fail("Could not find system prompt in function constants")

        assert "PRESERVE ALL original content" in prompt
        assert "Do NOT summarize" in prompt
        assert "Do NOT add any facts" in prompt
        assert "Only improve the FORMATTING" in prompt
        assert "Keep the original language and wording" in prompt
        assert "Output ONLY the formatted Markdown" in prompt
        assert "Do not translate" in prompt


class TestImportFlowRawJD:
    """Test the raw_jd scraping flow end-to-end logic."""

    def test_scraped_job_dataclass_fields(self):
        from app.modules.jobs.importer import ScrapedJob

        job = ScrapedJob(
            title="Test",
            company="TestCo",
            url="https://example.com",
            location="Berlin",
            raw_jd="Raw text",
            source="linkedin.com",
            source_job_id="123",
            posted_at=None,
            employment_type=None,
            workplace=None,
            salary_text=None,
            scraped_json={},
        )
        assert job.raw_jd == "Raw text"
        assert job.title == "Test"
        assert job.source == "linkedin.com"

    def test_normalize_text_handles_html_entities(self):
        from app.modules.jobs.importer import _normalize_text

        result = _normalize_text("Hello&amp;World &copy; 2024")
        assert "Hello&World" in result

    def test_clean_source_text_linkedin_removes_boilerplate(self):
        from app.modules.jobs.importer import _clean_source_text

        raw = (
            "About You\nSome text here.\n"
            "Responsibilities\n- Do task A\n- Do task B\n"
            "Requirements\n- Skill X\n"
            "People also viewed\nSimilar jobs at XYZ"
        )
        result = _clean_source_text("linkedin.com", raw)
        assert "Do task A" in result
        assert "Skill X" in result
        assert "People also viewed" not in result
        assert "Similar jobs" not in result

    def test_clean_source_text_linkedin_cuts_at_earliest_end_marker(self):
        from app.modules.jobs.importer import _clean_source_text

        raw = (
            "Responsibilities\n- Task 1\n- Task 2\n"
            "Requirements\n- Req 1\n"
            "Referrals increase your chances\nSome boilerplate"
        )
        result = _clean_source_text("linkedin.com", raw)
        assert "Task 1" in result
        assert "Req 1" in result
        assert "Referrals increase your chances" not in result

    def test_strip_html_removes_script_tags(self):
        from app.modules.jobs.importer import _strip_html

        result = _strip_html("<html><script>alert('x')</script><p>Job description here</p></html>")
        assert "alert" not in result
        assert "Job description here" in result

    def test_normalize_text_collapses_whitespace(self):
        from app.modules.jobs.importer import _normalize_text

        result = _normalize_text("Line   one\n\n\nLine   two  ")
        assert result == "Line one\n\nLine two"
