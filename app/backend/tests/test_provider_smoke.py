"""
Provider smoke tests that validate live LLM API keys are working.

These tests make real API calls. Run them with:
    cd app/backend && source .venv/bin/activate && PYTHONPATH=. pytest tests/test_provider_smoke.py -v

Each provider test is independent. The suite passes as long as at least one
configured provider responds successfully. Individual failures are warnings
so operators know which keys need attention.
"""

import asyncio
import os
import sys
import warnings
from dataclasses import dataclass

import pytest
from openai import AsyncOpenAI


@dataclass
class ProviderConfig:
    name: str
    api_key: str
    base_url: str
    model: str


def _gather_providers() -> list[ProviderConfig]:
    """Read provider configs from the same env vars as Settings."""
    providers: list[ProviderConfig] = []

    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        providers.append(
            ProviderConfig(
                name="gemini",
                api_key=gemini_key,
                base_url=os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"),
                model=os.getenv("GEMINI_MODEL_FAST", "gemini-3.1-flash-lite"),
            )
        )

    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
    if deepseek_key:
        providers.append(
            ProviderConfig(
                name="deepseek",
                api_key=deepseek_key,
                base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                model=os.getenv("DEEPSEEK_MODEL_FAST", "deepseek-v4-flash"),
            )
        )

    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    if openrouter_key:
        providers.append(
            ProviderConfig(
                name="openrouter",
                api_key=openrouter_key,
                base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
                model=os.getenv("OPENROUTER_MODEL_FAST", "deepseek/deepseek-v4-flash"),
            )
        )

    return providers


async def _check_provider(cfg: ProviderConfig) -> tuple[str, bool, str]:
    """Send a minimal chat request to one provider. Returns (name, ok, detail)."""
    client = AsyncOpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
    try:
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
            pytest.skip("No LLM API keys configured in environment")

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

        assert healthy, (
            f"All {len(providers)} provider(s) failed. "
            + " ".join(f"{r[0]}={r[2]}" for r in results)
        )
