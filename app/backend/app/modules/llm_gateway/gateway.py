import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import google.auth
import google.auth.transport.requests
from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.redis_client import cache
from app.db.models import LLMRun
from app.db.session import async_session_factory


@dataclass
class LLMProvider:
    name: str
    client: Any
    default_model: str
    quality_model: str
    reasoning_model: str


TASK_MODEL_TIERS = {
    "jd_format": "fast",
    "jd_extract": "quality",
    "fit_explanation": "fast",
    "resume_generate": "quality",
    "profile_extract": "quality",
}


class VertexAIClientRefresher:
    def __init__(self, *, project_id: str, location: str):
        self.credentials, detected_project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        self.project_id = project_id or detected_project
        if not self.project_id:
            raise RuntimeError("Vertex AI project id is not configured")
        self.location = location or "global"
        self.request = google.auth.transport.requests.Request()
        self.client = AsyncOpenAI(
            api_key="PLACEHOLDER",
            base_url=(
                "https://aiplatform.googleapis.com/v1/"
                f"projects/{self.project_id}/locations/{self.location}/endpoints/openapi"
            ),
        )

    def _refresh_if_needed(self) -> None:
        if not self.credentials.valid:
            self.credentials.refresh(self.request)
            if not self.credentials.valid:
                raise RuntimeError("Unable to refresh Vertex AI credentials")
        self.client.api_key = self.credentials.token

    @property
    def chat(self):
        self._refresh_if_needed()
        return self.client.chat


class LLMGateway:
    def __init__(self):
        settings = get_settings()
        self.providers = self._build_providers(settings)
        if not self.providers:
            raise RuntimeError(
                "No LLM provider configured. "
                "Configure Vertex AI ADC, GEMINI_API_KEY, DEEPSEEK_API_KEY, or OPENROUTER_API_KEY."
            )
        self.provider = self.providers[0].name
        self.client = self.providers[0].client
        self.default_model = self.providers[0].default_model
        self.default_model_reasoning = self.providers[0].reasoning_model
        self.last_provider = self.provider
        self.last_model = self.default_model
        self.settings = settings

    def _build_gemini_provider(self, settings) -> LLMProvider | None:
        if not settings.gemini_api_key:
            return None
        return LLMProvider(
            name="gemini",
            client=AsyncOpenAI(api_key=settings.gemini_api_key, base_url=settings.gemini_base_url),
            default_model=settings.gemini_model_fast,
            quality_model=settings.gemini_model_quality,
            reasoning_model=settings.gemini_model_reasoning,
        )

    def _build_vertex_ai_provider(self, settings) -> LLMProvider | None:
        try:
            client = VertexAIClientRefresher(
                project_id=settings.vertex_ai_project_id or settings.google_cloud_project,
                location=settings.vertex_ai_location,
            )
        except Exception:
            return None

        return LLMProvider(
            name="vertex_ai",
            client=client,
            default_model=settings.vertex_ai_model_fast,
            quality_model=settings.vertex_ai_model_quality,
            reasoning_model=settings.vertex_ai_model_reasoning,
        )

    def _build_openai_provider(
        self,
        *,
        name: str,
        api_key: str,
        base_url: str,
        model_fast: str,
        model_quality: str,
        model_reasoning: str,
    ) -> LLMProvider | None:
        if not api_key:
            return None
        return LLMProvider(
            name=name,
            client=AsyncOpenAI(api_key=api_key, base_url=base_url),
            default_model=model_fast,
            quality_model=model_quality,
            reasoning_model=model_reasoning,
        )

    def _build_providers(self, settings) -> list[LLMProvider]:
        preferred = (settings.llm_provider or "vertex_ai").lower()
        ordered_names = list(
            dict.fromkeys([preferred, "vertex_ai", "gemini", "deepseek", "openrouter"])
        )
        providers: list[LLMProvider] = []
        for name in ordered_names:
            provider = None
            if name == "vertex_ai":
                provider = self._build_vertex_ai_provider(settings)
            elif name == "gemini":
                provider = self._build_gemini_provider(settings)
            elif name == "deepseek":
                provider = self._build_openai_provider(
                    name="deepseek",
                    api_key=settings.deepseek_api_key,
                    base_url=settings.deepseek_base_url,
                    model_fast=settings.deepseek_model_fast,
                    model_quality=settings.deepseek_model_quality,
                    model_reasoning=settings.deepseek_model_reasoning,
                )
            elif name == "openrouter":
                provider = self._build_openai_provider(
                    name="openrouter",
                    api_key=settings.openrouter_api_key,
                    base_url=settings.openrouter_base_url,
                    model_fast=settings.openrouter_model_fast,
                    model_quality=settings.openrouter_model_quality,
                    model_reasoning=settings.openrouter_model_reasoning,
                )
            if provider:
                providers.append(provider)
        return providers

    async def run_text(
        self,
        tenant_id: UUID,
        task: str,
        prompt_version: str,
        messages: list[dict],
        model: str | None = None,
        model_tier: str | None = None,
        reasoning: bool = False,
        response_format: dict | None = None,
    ) -> str:
        input_text = json.dumps(messages, sort_keys=True)
        input_hash = hashlib.sha256(input_text.encode()).hexdigest()[:16]
        last_error: Exception | None = None

        for provider in self.providers:
            selected_model = self._select_model(provider, task, model, model_tier, reasoning)

            cache_key_parts = [str(tenant_id), task, selected_model, prompt_version, input_hash]
            cached = await cache.get("llm", *cache_key_parts)
            if cached is not None:
                await self._log_run(
                    tenant_id=tenant_id,
                    task=task,
                    provider=provider.name,
                    prompt_version=prompt_version,
                    model=selected_model,
                    input_hash=input_hash,
                    latency_ms=0,
                    tokens_json=None,
                    status="cache_hit",
                )
                self.provider = provider.name
                self.last_provider = provider.name
                self.last_model = selected_model
                return cached

            start = time.monotonic()
            kwargs: dict[str, Any] = dict(
                model=selected_model,
                messages=messages,
                temperature=0.3,
            )
            if response_format:
                kwargs["response_format"] = response_format

            try:
                response = await provider.client.chat.completions.create(**kwargs)
                latency_ms = int((time.monotonic() - start) * 1000)

                content = response.choices[0].message.content or ""

                tokens = None
                if response.usage:
                    tokens = {
                        "prompt": response.usage.prompt_tokens,
                        "completion": response.usage.completion_tokens,
                        "total": response.usage.total_tokens,
                    }

                await self._log_run(
                    tenant_id=tenant_id,
                    task=task,
                    provider=provider.name,
                    prompt_version=prompt_version,
                    model=selected_model,
                    input_hash=input_hash,
                    latency_ms=latency_ms,
                    tokens_json=tokens,
                    status="success",
                )

                await cache.set("llm", *cache_key_parts, value=content)

                self.provider = provider.name
                self.client = provider.client
                self.last_provider = provider.name
                self.last_model = selected_model
                return content

            except Exception as e:
                latency_ms = int((time.monotonic() - start) * 1000)
                await self._log_run(
                    tenant_id=tenant_id,
                    task=task,
                    provider=provider.name,
                    prompt_version=prompt_version,
                    model=selected_model,
                    input_hash=input_hash,
                    latency_ms=latency_ms,
                    tokens_json=None,
                    status="error",
                    error_message=str(e),
                )
                last_error = e

        if last_error:
            raise last_error
        raise RuntimeError("No LLM provider available")

    async def run_json(
        self,
        tenant_id: UUID,
        task: str,
        prompt_version: str,
        messages: list[dict],
        output_schema: type[BaseModel],
        model: str | None = None,
        model_tier: str | None = None,
        thinking: bool = False,
    ) -> BaseModel:
        content = await self.run_text(
            tenant_id=tenant_id,
            task=task,
            prompt_version=prompt_version,
            messages=messages,
            model=model,
            model_tier=model_tier,
            reasoning=thinking,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(content or "{}")
        return output_schema(**parsed)

    @staticmethod
    def _select_model(
        provider: LLMProvider,
        task: str,
        model: str | None,
        model_tier: str | None,
        reasoning: bool,
    ) -> str:
        if model:
            return model
        if reasoning:
            return provider.reasoning_model
        tier = model_tier or TASK_MODEL_TIERS.get(task, "fast")
        if tier == "quality":
            return provider.quality_model or provider.default_model
        if tier == "reasoning":
            return provider.reasoning_model
        return provider.default_model

    async def _log_run(self, **kwargs: Any) -> None:
        try:
            async with async_session_factory() as session:
                run = LLMRun(
                    id=uuid.uuid4(),
                    tenant_id=kwargs["tenant_id"],
                    task=kwargs["task"],
                    provider=kwargs.get("provider", self.provider),
                    model=kwargs["model"],
                    prompt_version=kwargs.get("prompt_version"),
                    input_hash=kwargs.get("input_hash"),
                    latency_ms=kwargs.get("latency_ms", 0),
                    tokens_json=kwargs.get("tokens_json"),
                    status=kwargs["status"],
                    error_message=kwargs.get("error_message"),
                )
                session.add(run)
                await session.commit()
        except Exception:
            pass


async def get_gateway() -> LLMGateway:
    return LLMGateway()
