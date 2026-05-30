from types import SimpleNamespace
from uuid import UUID

from app.modules.resumes.artifacts import build_resume_object_keys
from app.modules.resumes.prompt_builder import build_llm_prompt
from app.modules.resumes.renderer_html import render_resume_html


def test_resume_prompt_builder_preserves_context_and_confirmed_skills():
    profile = SimpleNamespace(
        raw_cv_md="## Summary\nBackend engineer",
        full_name="Ada Lovelace",
        headline="Senior Backend Engineer",
    )

    messages = build_llm_prompt(
        profile,
        {"title": "Platform Engineer", "company": "Example GmbH"},
        confirmed_skills=["Python", "Kubernetes"],
    )

    assert messages[0]["role"] == "system"
    assert "DACH-format resume writer" in messages[0]["content"]
    assert "Ada Lovelace" in messages[1]["content"]
    assert "Platform Engineer" in messages[1]["content"]
    assert "Python, Kubernetes" in messages[1]["content"]


def test_resume_html_renderer_includes_profile_job_and_sections():
    profile = SimpleNamespace(
        full_name="Ada Lovelace",
        headline="Senior Backend Engineer",
        location="Berlin",
        timezone="CET",
        raw_cv_md=(
            "## Summary\nBuilds reliable platforms.\n"
            "## Skills\n- Python\n"
            "## Experience\n- Built APIs\n"
            "## Education\n- MSc Computer Science"
        ),
    )

    html, provenance = render_resume_html(
        profile, {"title": "Platform Engineer", "company": "Example GmbH"}
    )

    assert provenance == {}
    assert "<h1>Ada Lovelace</h1>" in html
    assert "Platform Engineer &mdash; Example GmbH" in html
    assert "Qualifikationen &amp; Skills" in html
    assert "<li>Python</li>" in html


def test_resume_artifact_object_keys_are_stable():
    job_id = UUID("11111111-1111-1111-1111-111111111111")
    file_id = UUID("22222222-2222-2222-2222-222222222222")

    assert build_resume_object_keys(job_id, file_id) == (
        "resumes/11111111-1111-1111-1111-111111111111/22222222-2222-2222-2222-222222222222.html",
        "resumes/11111111-1111-1111-1111-111111111111/22222222-2222-2222-2222-222222222222.pdf",
    )
