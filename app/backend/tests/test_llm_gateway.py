from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.llm_gateway.gateway import LLMGateway, LLMProvider


class _FakeCompletions:
    def __init__(
        self, provider_name: str, content: str | None = None, error: Exception | None = None
    ):
        self.provider_name = provider_name
        self.content = content
        self.error = error
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.content),
                )
            ],
            usage=None,
        )


def _provider(name: str, completions: _FakeCompletions) -> LLMProvider:
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=completions,
        )
    )
    return LLMProvider(
        name=name,
        client=client,
        default_model=f"{name}-fast",
        quality_model=f"{name}-quality",
        reasoning_model=f"{name}-reasoning",
    )


def _provider_settings(llm_provider: str = "gemini") -> SimpleNamespace:
    return SimpleNamespace(
        llm_provider=llm_provider,
        vertex_ai_project_id="vertex-project",
        google_cloud_project="google-project",
        vertex_ai_location="global",
        vertex_ai_model_fast="vertex-fast",
        vertex_ai_model_quality="vertex-quality",
        vertex_ai_model_reasoning="vertex-reasoning",
        deepseek_api_key="deepseek-key",
        deepseek_base_url="https://deepseek.example",
        deepseek_model_fast="deepseek-fast",
        deepseek_model_quality="deepseek-quality",
        deepseek_model_reasoning="deepseek-reasoning",
        openrouter_api_key="openrouter-key",
        openrouter_base_url="https://openrouter.example",
        openrouter_model_fast="openrouter-fast",
        openrouter_model_quality="openrouter-quality",
        openrouter_model_reasoning="openrouter-reasoning",
    )


def test_build_providers_prefers_gemini(monkeypatch):
    gateway = LLMGateway.__new__(LLMGateway)
    monkeypatch.setattr(
        gateway,
        "_build_vertex_ai_provider",
        lambda settings: _provider("vertex_ai", _FakeCompletions("vertex_ai")),
    )
    monkeypatch.setattr(
        gateway,
        "_build_gemini_provider",
        lambda settings: _provider("gemini", _FakeCompletions("gemini")),
    )
    monkeypatch.setattr(
        gateway,
        "_build_openai_provider",
        lambda **kwargs: _provider(kwargs["name"], _FakeCompletions(kwargs["name"])),
    )

    providers = gateway._build_providers(_provider_settings("gemini"))

    assert [provider.name for provider in providers] == [
        "gemini",
        "vertex_ai",
        "deepseek",
        "openrouter",
    ]


def test_build_providers_prefers_vertex_ai(monkeypatch):
    gateway = LLMGateway.__new__(LLMGateway)
    monkeypatch.setattr(
        gateway,
        "_build_vertex_ai_provider",
        lambda settings: _provider("vertex_ai", _FakeCompletions("vertex_ai")),
    )
    monkeypatch.setattr(
        gateway,
        "_build_gemini_provider",
        lambda settings: _provider("gemini", _FakeCompletions("gemini")),
    )
    monkeypatch.setattr(
        gateway,
        "_build_openai_provider",
        lambda **kwargs: _provider(kwargs["name"], _FakeCompletions(kwargs["name"])),
    )

    providers = gateway._build_providers(_provider_settings("vertex_ai"))

    assert [provider.name for provider in providers] == [
        "vertex_ai",
        "gemini",
        "deepseek",
        "openrouter",
    ]


def test_build_vertex_ai_provider_uses_vertex_models(monkeypatch):
    import app.modules.llm_gateway.gateway as gateway_module

    class _FakeVertexClient:
        def __init__(self, *, project_id: str, location: str):
            self.project_id = project_id
            self.location = location

    monkeypatch.setattr(gateway_module, "VertexAIClientRefresher", _FakeVertexClient)
    gateway = LLMGateway.__new__(LLMGateway)

    provider = gateway._build_vertex_ai_provider(_provider_settings("vertex_ai"))

    assert provider is not None
    assert provider.name == "vertex_ai"
    assert provider.default_model == "vertex-fast"
    assert provider.quality_model == "vertex-quality"
    assert provider.reasoning_model == "vertex-reasoning"
    assert provider.client.project_id == "vertex-project"
    assert provider.client.location == "global"


@pytest.mark.asyncio
async def test_run_text_falls_back_after_provider_error(monkeypatch):
    gateway = LLMGateway.__new__(LLMGateway)
    gemini = _FakeCompletions("gemini", error=RuntimeError("gemini timeout"))
    deepseek = _FakeCompletions("deepseek", content="ok")
    gateway.providers = [
        _provider("gemini", gemini),
        _provider("deepseek", deepseek),
    ]
    gateway.last_provider = "gemini"
    gateway.last_model = "gemini-fast"

    logs = []

    async def _capture_log(**kwargs):
        logs.append(kwargs)

    monkeypatch.setattr(gateway, "_log_run", _capture_log)

    result = await gateway.run_text(
        tenant_id=uuid4(),
        task="test",
        prompt_version="1",
        messages=[{"role": "user", "content": "hello"}],
    )

    assert result == "ok"
    assert [log["provider"] for log in logs] == ["gemini", "deepseek"]
    assert [log["status"] for log in logs] == ["error", "success"]
    assert gateway.last_provider == "deepseek"
    assert gateway.last_model == "deepseek-fast"


@pytest.mark.asyncio
async def test_run_text_falls_back_after_vertex_error(monkeypatch):
    gateway = LLMGateway.__new__(LLMGateway)
    vertex = _FakeCompletions("vertex_ai", error=RuntimeError("vertex unavailable"))
    deepseek = _FakeCompletions("deepseek", content="ok")
    gateway.providers = [
        _provider("vertex_ai", vertex),
        _provider("deepseek", deepseek),
    ]
    gateway.last_provider = "vertex_ai"
    gateway.last_model = "vertex_ai-fast"

    logs = []

    async def _capture_log(**kwargs):
        logs.append(kwargs)

    monkeypatch.setattr(gateway, "_log_run", _capture_log)

    result = await gateway.run_text(
        tenant_id=uuid4(),
        task="jd_extract",
        prompt_version="1",
        messages=[{"role": "user", "content": "hello"}],
    )

    assert result == "ok"
    assert [log["provider"] for log in logs] == ["vertex_ai", "deepseek"]
    assert [log["status"] for log in logs] == ["error", "success"]
    assert [log["model"] for log in logs] == ["vertex_ai-quality", "deepseek-quality"]
    assert gateway.last_provider == "deepseek"
    assert gateway.last_model == "deepseek-quality"


class TestModelSelection:
    def test_fast_tier_for_jd_format(self):
        from app.modules.llm_gateway.gateway import LLMGateway

        provider = _provider("gemini", _FakeCompletions("gemini"))
        model = LLMGateway._select_model(provider, "jd_format", None, None, False)
        assert model == "gemini-fast"

    def test_fast_tier_for_fit_explanation(self):
        from app.modules.llm_gateway.gateway import LLMGateway

        provider = _provider("gemini", _FakeCompletions("gemini"))
        model = LLMGateway._select_model(provider, "fit_explanation", None, None, False)
        assert model == "gemini-fast"

    def test_quality_tier_for_jd_extract(self):
        from app.modules.llm_gateway.gateway import LLMGateway

        provider = _provider("gemini", _FakeCompletions("gemini"))
        model = LLMGateway._select_model(provider, "jd_extract", None, None, False)
        assert model == "gemini-quality"

    def test_quality_tier_for_resume_generate(self):
        from app.modules.llm_gateway.gateway import LLMGateway

        provider = _provider("gemini", _FakeCompletions("gemini"))
        model = LLMGateway._select_model(provider, "resume_generate", None, None, False)
        assert model == "gemini-quality"

    def test_quality_tier_for_profile_extract(self):
        from app.modules.llm_gateway.gateway import LLMGateway

        provider = _provider("gemini", _FakeCompletions("gemini"))
        model = LLMGateway._select_model(provider, "profile_extract", None, None, False)
        assert model == "gemini-quality"

    def test_unknown_task_defaults_to_fast(self):
        from app.modules.llm_gateway.gateway import LLMGateway

        provider = _provider("gemini", _FakeCompletions("gemini"))
        model = LLMGateway._select_model(provider, "unknown_task", None, None, False)
        assert model == "gemini-fast"

    def test_reasoning_overrides_task_tier(self):
        from app.modules.llm_gateway.gateway import LLMGateway

        provider = _provider("gemini", _FakeCompletions("gemini"))
        model = LLMGateway._select_model(provider, "jd_format", None, None, True)
        assert model == "gemini-reasoning"

    def test_explicit_model_overrides_all(self):
        from app.modules.llm_gateway.gateway import LLMGateway

        provider = _provider("gemini", _FakeCompletions("gemini"))
        model = LLMGateway._select_model(provider, "jd_extract", "custom-model", "quality", True)
        assert model == "custom-model"

    def test_explicit_model_tier_overrides_task_map(self):
        from app.modules.llm_gateway.gateway import LLMGateway

        provider = _provider("gemini", _FakeCompletions("gemini"))
        model = LLMGateway._select_model(provider, "jd_format", None, "quality", False)
        assert model == "gemini-quality"

    def test_reasoning_tier_selects_reasoning_model(self):
        from app.modules.llm_gateway.gateway import LLMGateway

        provider = _provider("gemini", _FakeCompletions("gemini"))
        model = LLMGateway._select_model(provider, "jd_format", None, "reasoning", False)
        assert model == "gemini-reasoning"


@pytest.mark.asyncio
async def test_run_text_passes_model_tier_to_provider(monkeypatch):
    gateway = LLMGateway.__new__(LLMGateway)
    gemini = _FakeCompletions("gemini", content="ok")
    gateway.providers = [_provider("gemini", gemini)]
    gateway.last_provider = "gemini"
    gateway.last_model = "gemini-fast"

    logs = []

    async def _capture_log(**kwargs):
        logs.append(kwargs)

    monkeypatch.setattr(gateway, "_log_run", _capture_log)

    await gateway.run_text(
        tenant_id=uuid4(),
        task="jd_extract",
        prompt_version="1",
        messages=[{"role": "user", "content": "hello"}],
    )

    assert logs[0]["model"] == "gemini-quality"


@pytest.mark.asyncio
async def test_run_json_forwards_model_tier(monkeypatch):
    from pydantic import BaseModel

    class _TestSchema(BaseModel):
        value: str

    gateway = LLMGateway.__new__(LLMGateway)
    gemini = _FakeCompletions("gemini", content='{"value": "ok"}')
    gateway.providers = [_provider("gemini", gemini)]
    gateway.last_provider = "gemini"
    gateway.last_model = "gemini-fast"

    logs = []

    async def _capture_log(**kwargs):
        logs.append(kwargs)

    monkeypatch.setattr(gateway, "_log_run", _capture_log)

    await gateway.run_json(
        tenant_id=uuid4(),
        task="resume_generate",
        prompt_version="1",
        messages=[{"role": "user", "content": "hello"}],
        output_schema=_TestSchema,
    )

    assert logs[0]["model"] == "gemini-quality"
