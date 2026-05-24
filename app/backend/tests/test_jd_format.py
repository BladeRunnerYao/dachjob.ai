"""
Tests for the JD formatting pipeline (format_raw_jd).

Run with:
    cd app/backend && source .venv/bin/activate && PYTHONPATH=. python3 -m pytest tests/test_jd_format.py -v
"""

from types import SimpleNamespace
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

    def test_linkedin_description_prefers_job_description_markup(self):
        from app.modules.jobs.importer import _linkedin_description_from_html

        html = """
        <body>
          <section>Use AI to assess how you fit Sign in to tailor your resume</section>
          <div class="show-more-less-html__markup show-more-less-html__markup--clamp-after-5">
            <strong>What awaits you?<br></strong>
            <ul><li>Build production-grade AI systems.</li></ul>
            <strong>What should you bring along?<br></strong>
            <ul><li>Strong hands-on Python skills.</li></ul>
          </div>
        </body>
        """

        result = _linkedin_description_from_html(html)

        assert result
        assert "Use AI to assess" not in result
        assert "Build production-grade AI systems" in result
        assert "Strong hands-on Python skills" in result

    def test_bmwgroup_uses_plain_request_headers(self):
        from app.modules.jobs.importer import _request_headers_for_url

        bmw_headers = _request_headers_for_url(
            "https://www.bmwgroup.jobs/de/en/jobfinder/job-description-copy.182180.html"
        )
        greenhouse_headers = _request_headers_for_url(
            "https://job-boards.greenhouse.io/contentful/jobs/7760966"
        )

        assert "Chrome" not in bmw_headers["User-Agent"]
        assert "Chrome" in greenhouse_headers["User-Agent"]

    def test_bmwgroup_description_and_attributes_from_html(self):
        from app.modules.jobs.importer import (
            _bmwgroup_company_from_html,
            _bmwgroup_description_from_html,
            _bmwgroup_employment_type_from_html,
            _bmwgroup_location_from_html,
            _bmwgroup_posted_at_from_html,
        )

        html = """
        <div class="cmp-container no-spacing grp-jobdescription__content text">
          <div class="cmp-text">
            <p><strong>ARE YOU PREPARED FOR THE FUTURE?</strong></p>
            <p>Artificial Intelligence and machine learning are at the cutting edge.</p>
          </div>
          <div class="cmp-text" itemprop="description">
            <p>We are an international team.</p>
            <p><strong>What awaits you?</strong></p>
            <ul><li>You design data pipelines.</li></ul>
            <p><strong>What should you bring along?</strong></p>
            <ul><li>Python and PyTorch experience.</li></ul>
          </div>
        </div>
        <div itemprop="hiringOrganization" itemscope itemtype="https://schema.org/Organization">
          <div class="grp-jobdescription__item grp-jobdescription__jobLegalEntity" itemprop="name">BMW AG</div>
        </div>
        <div class="grp-jobdescription__item grp-jobdescription__jobLocation">Munich</div>
        <div class="grp-hidden" itemprop="datePosted">20260327</div>
        <div class="grp-hidden" itemprop="employmentType">Full-time</div>
        """

        description = _bmwgroup_description_from_html(html)

        assert description
        assert "ARE YOU PREPARED" in description
        assert "You design data pipelines" in description
        assert _bmwgroup_company_from_html(html) == "BMW AG"
        assert _bmwgroup_location_from_html(html) == "Munich"
        assert _bmwgroup_employment_type_from_html(html) == "Full-time"
        assert _bmwgroup_posted_at_from_html(html).year == 2026

    def test_normalize_text_collapses_whitespace(self):
        from app.modules.jobs.importer import _normalize_text

        result = _normalize_text("Line   one\n\n\nLine   two  ")
        assert result == "Line one\n\nLine two"

    def test_greenhouse_html_detection_from_custom_careers_page(self):
        from app.modules.jobs.importer import (
            _greenhouse_board_from_html,
            _greenhouse_board_from_known_host,
            _greenhouse_board_from_url,
            _greenhouse_job_id_from_url_or_html,
        )

        html = """
        <meta name="api_id" content="7581804"/>
        <script>
          const jobId = '7581804'
          fetch(`https://boards-api.greenhouse.io/v1/boards/getyourguide/jobs/${jobId}`)
        </script>
        """

        assert _greenhouse_board_from_html(html) == "getyourguide"
        assert (
            _greenhouse_job_id_from_url_or_html(
                "https://getyourguide.careers/jobs/7581804?gh_jid=7581804", html
            )
            == "7581804"
        )
        assert (
            _greenhouse_board_from_url(
                "https://job-boards.greenhouse.io/embed/job_app/confirmation?for=yoodliinc&token=4246665009"
            )
            == "yoodliinc"
        )
        assert (
            _greenhouse_job_id_from_url_or_html(
                "https://job-boards.greenhouse.io/embed/job_app/confirmation?for=yoodliinc&token=4246665009",
                "",
            )
            == "4246665009"
        )
        assert (
            _greenhouse_board_from_known_host(
                "https://traderepublic.com/en-de/about?jobId=7685049003"
            )
            == "traderepublicbank"
        )
        assert (
            _greenhouse_job_id_from_url_or_html(
                "https://traderepublic.com/en-de/about?jobId=7685049003", ""
            )
            == "7685049003"
        )

    def test_known_non_job_pages_are_rejected(self):
        from app.modules.jobs.importer import _looks_like_non_job_page

        assert _looks_like_non_job_page(
            "google.com",
            "https://www.google.com/about/careers/applications/jobs/results/74466962196832966",
            "Jobs search — Google Careers",
        )
        assert _looks_like_non_job_page(
            "linkedin.com",
            "https://www.linkedin.com/jobs/view/4415808773/",
            "795 Jobs für Php Entwickler in Deutschland",
        )
        assert _looks_like_non_job_page(
            "job-boards.greenhouse.io",
            "https://job-boards.greenhouse.io/embed/job_app/confirmation?for=yoodliinc&token=4246665009",
            "Thank you for applying",
        )

    @pytest.mark.asyncio
    async def test_scrape_greenhouse_custom_page_uses_api_content(self, monkeypatch):
        from app.modules.jobs.importer import scrape_job_url

        class FakeResponse:
            def __init__(self, url, text="", payload=None, status_code=200):
                self.url = url
                self.text = text
                self._payload = payload
                self.status_code = status_code

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise RuntimeError(f"HTTP {self.status_code}")

            def json(self):
                return self._payload

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def get(self, url, **kwargs):
                if "boards-api.greenhouse.io/v1/boards/getyourguide/jobs/7581804" in url:
                    return FakeResponse(
                        url,
                        payload={
                            "id": 7581804,
                            "title": "Senior Software Engineer, Search Platform",
                            "location": {"name": "Berlin"},
                            "content": (
                                "&lt;h3&gt;Team mission&lt;/h3&gt;"
                                "&lt;p&gt;Build search platform systems.&lt;/p&gt;"
                                "&lt;h3&gt;Your toolkit&lt;/h3&gt;"
                                "&lt;ul&gt;&lt;li&gt;High proficiency in Java&lt;/li&gt;&lt;/ul&gt;"
                            ),
                            "departments": [{"name": "Engineering"}],
                            "offices": [{"name": "Berlin"}],
                        },
                    )
                if "boards-api.greenhouse.io/v1/boards/getyourguide" in url:
                    return FakeResponse(url, payload={"name": "GetYourGuide"})
                return FakeResponse(
                    url,
                    text=(
                        "<title>Senior Software Engineer, Search Platform | Jobs at GetYourGuide</title>"
                        '<meta name="api_id" content="7581804"/>'
                        '<div id="wrapper-el"></div>'
                        "<script>const jobId = '7581804'; "
                        "fetch(`https://boards-api.greenhouse.io/v1/boards/getyourguide/jobs/${jobId}`)</script>"
                        "<h3>Similar jobs</h3>"
                    ),
                )

        monkeypatch.setattr("app.modules.jobs.importer.httpx.AsyncClient", FakeClient)

        job = await scrape_job_url("https://getyourguide.careers/jobs/7581804?gh_jid=7581804")

        assert job.title == "Senior Software Engineer, Search Platform"
        assert job.company == "GetYourGuide"
        assert job.location == "Berlin"
        assert "Team mission" in job.raw_jd
        assert "High proficiency in Java" in job.raw_jd
        assert "Similar jobs" not in job.raw_jd
        assert job.scraped_json["ats_provider"] == "greenhouse"

    @pytest.mark.asyncio
    async def test_scrape_greenhouse_known_host_uses_api_content(self, monkeypatch):
        from app.modules.jobs.importer import scrape_job_url

        class FakeResponse:
            def __init__(self, url, text="", payload=None, status_code=200):
                self.url = url
                self.text = text
                self._payload = payload
                self.status_code = status_code

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise RuntimeError(f"HTTP {self.status_code}")

            def json(self):
                return self._payload

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def get(self, url, **kwargs):
                if "boards-api.greenhouse.io/v1/boards/helsing/jobs/4871604101" in url:
                    return FakeResponse(
                        url,
                        payload={
                            "id": 4871604101,
                            "title": "Finance Data Engineer",
                            "location": {"name": "Munich"},
                            "content": (
                                "<h3>Responsibilities</h3>"
                                "<ul><li>Build reliable data pipelines.</li></ul>"
                                "<h3>Requirements</h3>"
                                "<ul><li>Strong SQL and Python experience.</li></ul>"
                            ),
                        },
                    )
                if "boards-api.greenhouse.io/v1/boards/helsing" in url:
                    return FakeResponse(url, payload={"name": "Helsing"})
                return FakeResponse(
                    url,
                    text="<title>Finance Data Engineer</title><main>Loading job...</main>",
                )

        monkeypatch.setattr("app.modules.jobs.importer.httpx.AsyncClient", FakeClient)

        job = await scrape_job_url("https://helsing.ai/jobs/4871604101?gh_jid=4871604101")

        assert job.title == "Finance Data Engineer"
        assert job.company == "Helsing"
        assert job.location == "Munich"
        assert "Build reliable data pipelines" in job.raw_jd
        assert "Strong SQL and Python experience" in job.raw_jd
        assert job.scraped_json["greenhouse_board"] == "helsing"

    def test_import_flow_does_not_format_raw_jd_with_llm(self):
        import inspect

        from app.modules.jobs import importer

        source = inspect.getsource(importer.import_job_urls)
        assert "format_raw_jd" not in source


class TestSkillExtraction:
    def test_listed_skill_extraction_rejects_sentence_and_page_noise(self):
        from app.modules.matching.service import _extract_listed_skills

        result = _extract_listed_skills(
            "We use technologies including Java, Spring Boot, React, LangChain, "
            "this role in Bangalore, to work at DeepL, Index Ventures, IVP, "
            "please visit https://amazon.jobs."
        )

        for skill in ["Java", "Spring Boot", "React", "LangChain"]:
            assert skill in result
        for noise in ["this role in Bangalore", "to work at DeepL", "Index Ventures", "IVP"]:
            assert noise not in result

    def test_greenhouse_getyourguide_skills_split_must_and_nice(self):
        from app.modules.matching.service import _enrich_parsed_skills

        job = SimpleNamespace(
            title="Senior Software Engineer, Search Platform",
            company="GetYourGuide",
            location="Berlin",
            raw_jd="""
            Your mission
            - Work on the full stack with a variety of technologies and frameworks like Java, Spring Boot, PHP, Vue.js, TypeScript, SASS, Node.js, MySQL, PostgreSQL, GraphQL, Kafka, OpenSearch, Kubernetes

            Your toolkit
            - 6+ years of software development experience working with distributed systems or search engines.
            - High proficiency in Java
            - Experience designing and deploying large-scale distributed systems
            - Experience with building reliable and observable systems

            Extras that give you an edge
            - Experience working with search engines like Elasticsearch, OpenSearch, Apache Solr, or Apache Lucene
            - Experience with A/B testing, hypothesis building, and event-based analytics
            """,
        )

        parsed = _enrich_parsed_skills({"must_have_skills": [], "nice_to_have_skills": []}, job)

        for skill in [
            "Java",
            "Spring Boot",
            "PHP",
            "Vue.js",
            "TypeScript",
            "PostgreSQL",
            "GraphQL",
            "Kafka",
            "Kubernetes",
            "Distributed systems",
            "Observability",
        ]:
            assert skill in parsed["must_have_skills"]
        for skill in [
            "Elasticsearch",
            "Apache Solr",
            "Apache Lucene",
            "A/B testing",
            "Event-based analytics",
        ]:
            assert skill in parsed["nice_to_have_skills"]
        assert "Elasticsearch" not in parsed["must_have_skills"]

    def test_bonus_section_skills_stay_nice_to_have(self):
        from app.modules.matching.service import _enrich_parsed_skills

        job = SimpleNamespace(
            title="Robotics Wireless & Network Engineer",
            company="Amazon RIVR",
            location="Zürich",
            raw_jd="""
            What you must have
            - Solid knowledge of networking protocols (TCP/IP, UDP, WebRTC, gRPC, MQTT).
            - Strong proficiency with ROS2/DDS and middleware integration for real-time systems.
            - Experience working with Linux-based systems.

            Get some bonus points
            - Architectures: Familiarity with cloud-to-edge architectures and MEC (Multi-access Edge Computing) deployment.
            - Scripting: Scripting in Python or Go for testing and automation.
            """,
        )

        parsed = _enrich_parsed_skills({"must_have_skills": [], "nice_to_have_skills": []}, job)

        for skill in [
            "Networking",
            "TCP/IP",
            "UDP",
            "WebRTC",
            "gRPC",
            "MQTT",
            "ROS2/DDS",
            "Middleware integration",
            "Linux",
        ]:
            assert skill in parsed["must_have_skills"]
        for skill in ["Cloud-to-edge architecture", "Mobile Edge Computing", "Python", "Go"]:
            assert skill in parsed["nice_to_have_skills"]
        assert "Python" not in parsed["must_have_skills"]

    def test_linkedin_bmw_sections_and_benefits_are_classified(self):
        from app.modules.matching.service import _enrich_parsed_skills

        job = SimpleNamespace(
            title="Senior Agentic AI Engineer (f/m/x)",
            company="BMW Group",
            location="Munich, Bavaria, Germany",
            raw_jd="""
            Artificial Intelligence and machine learning are at the cutting edge when it comes to shaping next-gen mobility.

            What awaits you?
            - In this role, you will design, build and industrialise production-grade AI and GenAI solutions across different business domains.
            - You will build scalable AI systems, including model integration, orchestration, retrieval, evaluation, monitoring, guardrails and deployment.

            What should you bring along?
            - At least 5 years of professional software engineering experience, with strong hands-on Python skills.
            - Strong understanding of modern AI system design, including LLM integration, orchestration, RAG, evaluation, monitoring, APIs and deployment.
            - Practical experience with cloud-based engineering environments, preferably AWS or Azure, including CI/CD and modern DevOps practices.

            What do we offer?
            - Annual special payments such as vacation pay, Christmas bonus, and profit sharing.
            - Flexible working hours including 6 weeks annual leave and overtime compensation.
            """,
        )

        parsed = _enrich_parsed_skills({"must_have_skills": [], "nice_to_have_skills": []}, job)

        for skill in [
            "Python",
            "Machine Learning",
            "GenAI",
            "LLMs",
            "RAG",
            "AWS",
            "Azure",
            "CI/CD pipelines",
            "Monitoring",
        ]:
            assert skill in parsed["must_have_skills"]
        for noise in ["Christmas bonus", "6 weeks annual leave", "Hiring"]:
            assert noise not in parsed["skills"]
