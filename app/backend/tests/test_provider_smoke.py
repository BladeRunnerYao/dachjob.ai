"""
Provider smoke tests that validate live LLM API keys are working.

These tests make real API calls. Run them with:
    cd app/backend
    source .venv/bin/activate
    PYTHONPATH=. pytest tests/test_provider_smoke.py -v

Each provider test is independent. The suite passes as long as at least one
configured provider responds successfully. Individual failures are warnings
so operators know which keys need attention.
"""

import asyncio
import os
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from openai import AsyncOpenAI

from app.modules.llm_gateway.gateway import VertexAIClientRefresher


@dataclass
class ProviderConfig:
    name: str
    model: str
    create_client: Callable[[], Any]


def _vertex_client_factory(project_id: str, location: str) -> Callable[[], Any]:
    def _create_client() -> Any:
        return VertexAIClientRefresher(project_id=project_id, location=location)

    return _create_client


def _openai_client_factory(api_key: str, base_url: str) -> Callable[[], AsyncOpenAI]:
    def _create_client() -> AsyncOpenAI:
        return AsyncOpenAI(api_key=api_key, base_url=base_url)

    return _create_client


def _gather_providers() -> list[ProviderConfig]:
    """Read provider configs from the same env vars as Settings."""
    providers: list[ProviderConfig] = []

    preferred_provider = os.getenv("LLM_PROVIDER", "").lower()
    vertex_project_id = (
        os.getenv("VERTEX_AI_PROJECT_ID")
        or os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("PROJECT_ID")
        or ""
    )
    vertex_requested = preferred_provider in {"vertex_ai", "vertex", "vertex-ai"}
    if vertex_requested or vertex_project_id:
        vertex_location = os.getenv("VERTEX_AI_LOCATION", "global")
        providers.append(
            ProviderConfig(
                name="vertex_ai",
                model=os.getenv("VERTEX_AI_MODEL_FAST", "google/gemini-3.1-flash-lite"),
                create_client=_vertex_client_factory(vertex_project_id, vertex_location),
            )
        )

    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        gemini_base_url = os.getenv(
            "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
        )
        providers.append(
            ProviderConfig(
                name="gemini",
                model=os.getenv("GEMINI_MODEL_FAST", "gemini-3.1-flash-lite"),
                create_client=_openai_client_factory(gemini_key, gemini_base_url),
            )
        )

    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
    if deepseek_key:
        deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        providers.append(
            ProviderConfig(
                name="deepseek",
                model=os.getenv("DEEPSEEK_MODEL_FAST", "deepseek-v4-flash"),
                create_client=_openai_client_factory(deepseek_key, deepseek_base_url),
            )
        )

    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    if openrouter_key:
        openrouter_base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        providers.append(
            ProviderConfig(
                name="openrouter",
                model=os.getenv("OPENROUTER_MODEL_FAST", "deepseek/deepseek-v4-flash"),
                create_client=_openai_client_factory(openrouter_key, openrouter_base_url),
            )
        )

    return providers


async def _check_provider(cfg: ProviderConfig) -> tuple[str, bool, str]:
    """Send a minimal chat request to one provider. Returns (name, ok, detail)."""
    try:
        client = cfg.create_client()
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=cfg.model,
                messages=[{"role": "user", "content": 'Reply with exactly "OK".'}],
                temperature=0,
                max_tokens=5,
            ),
            timeout=30,
        )
        content = (response.choices[0].message.content or "").strip()
        if "OK" in content:
            return cfg.name, True, f"model={cfg.model}"
        return cfg.name, False, f"unexpected response: {content!r}"
    except Exception as e:
        return cfg.name, False, f"{type(e).__name__}: {e}"


class TestProviderSmoke:
    """Live API smoke tests — each provider gets its own test case."""

    @pytest.mark.asyncio
    async def test_at_least_one_provider_works(self):
        providers = _gather_providers()
        if not providers:
            pytest.skip("No LLM providers configured in environment")

        results = []
        for cfg in providers:
            name, ok, detail = await _check_provider(cfg)
            results.append((name, ok, detail))
            if ok:
                print(f"  [OK] {name} ({detail})")
            else:
                warnings.warn(f"Provider '{name}' is unhealthy: {detail}")

        healthy = [r for r in results if r[1]]
        unhealthy = [r for r in results if not r[1]]

        print(f"\n  Healthy:   {[r[0] for r in healthy] if healthy else 'none'}")
        print(f"  Unhealthy: {[r[0] for r in unhealthy] if unhealthy else 'none'}")

        assert healthy, f"All {len(providers)} provider(s) failed. " + " ".join(
            f"{r[0]}={r[2]}" for r in results
        )
