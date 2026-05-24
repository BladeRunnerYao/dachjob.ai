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
from app.db.models import LLMRun
from app.db.session import async_session_factory


@dataclass(frozen=True)
class LLMProvider:
    name: str
    client: AsyncOpenAI
    default_model: str
    reasoning_model: str


class LLMGateway:
    def __init__(self):
        settings = get_settings()
        self.settings = settings
        self.providers = self._build_providers(settings)
        if not self.providers:
            raise RuntimeError(
                "No LLM API key configured. "
                "Configure Vertex AI Gemini auth, DEEPSEEK_API_KEY, or OPENROUTER_API_KEY."
            )

        primary = self.providers[0]
        self.provider = primary.name
        self.default_model = primary.default_model
        self.default_model_reasoning = primary.reasoning_model
        self.last_provider = primary.name
        self.last_model = primary.default_model

    def _build_providers(self, settings) -> list[LLMProvider]:
        configured = {
            "gemini": self._build_gemini_provider(settings),
            "deepseek": self._build_openai_provider(
                name="deepseek",
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                default_model=settings.deepseek_model_fast,
                reasoning_model=settings.deepseek_model_reasoning,
            ),
            "openrouter": self._build_openai_provider(
                name="openrouter",
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
                default_model=settings.openrouter_model_fast,
                reasoning_model=settings.openrouter_model_reasoning,
            ),
        }

        preferred = (settings.llm_provider or "gemini").lower()
        if preferred in ("auto", "fallback"):
            order = ["gemini", "deepseek", "openrouter"]
        elif preferred in configured:
            order = [preferred] + [
                name for name in ("gemini", "deepseek", "openrouter") if name != preferred
            ]
        else:
            order = ["gemini", "deepseek", "openrouter"]

        return [configured[name] for name in order if configured[name] is not None]

    def _build_openai_provider(
        self,
        *,
        name: str,
        api_key: str,
        base_url: str,
        default_model: str,
        reasoning_model: str,
    ) -> LLMProvider | None:
        if not api_key:
            return None
        return LLMProvider(
            name=name,
            client=AsyncOpenAI(api_key=api_key, base_url=base_url),
            default_model=default_model,
            reasoning_model=reasoning_model,
        )

    def _build_gemini_provider(self, settings) -> LLMProvider | None:
        project_id = settings.gemini_project_id or settings.google_cloud_project
        if not project_id:
            return None

        try:
            credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            credentials.refresh(google.auth.transport.requests.Request())
        except Exception:
            return None

        base_url = (
            "https://aiplatform.googleapis.com/v1/"
            f"projects/{project_id}/locations/{settings.gemini_location}/endpoints/openapi"
        )
        return LLMProvider(
            name="gemini",
            client=AsyncOpenAI(api_key=credentials.token, base_url=base_url),
            default_model=settings.gemini_model_fast,
            reasoning_model=settings.gemini_model_reasoning,
        )

    async def run_text(
        self,
        tenant_id: UUID,
        task: str,
        prompt_version: str,
        messages: list[dict],
        model: str | None = None,
        reasoning: bool = False,
        response_format: dict | None = None,
    ) -> str:
        input_text = json.dumps(messages, sort_keys=True)
        input_hash = hashlib.sha256(input_text.encode()).hexdigest()[:16]

        last_error: Exception | None = None
        for provider in self.providers:
            attempt_start = time.monotonic()
            attempt_model = model or (
                provider.reasoning_model if reasoning else provider.default_model
            )
            kwargs: dict[str, Any] = dict(
                model=attempt_model,
                messages=messages,
                temperature=0.3,
            )
            if reasoning and provider.name == "openrouter":
                kwargs["extra_body"] = {"reasoning": {"enabled": True}}
            if reasoning and provider.name == "gemini":
                kwargs["reasoning_effort"] = "low"
            if response_format:
                kwargs["response_format"] = response_format

            try:
                response = await provider.client.chat.completions.create(**kwargs)
                latency_ms = int((time.monotonic() - attempt_start) * 1000)

                content = response.choices[0].message.content or ""

                tokens = None
                if response.usage:
                    tokens = {
                        "prompt": response.usage.prompt_tokens,
                        "completion": response.usage.completion_tokens,
                        "total": response.usage.total_tokens,
                    }

                self.last_provider = provider.name
                self.last_model = attempt_model
                await self._log_run(
                    tenant_id=tenant_id,
                    task=task,
                    prompt_version=prompt_version,
                    provider=provider.name,
                    model=attempt_model,
                    input_hash=input_hash,
                    latency_ms=latency_ms,
                    tokens_json=tokens,
                    status="success",
                )

                return content

            except Exception as e:
                last_error = e
                latency_ms = int((time.monotonic() - attempt_start) * 1000)
                await self._log_run(
                    tenant_id=tenant_id,
                    task=task,
                    prompt_version=prompt_version,
                    provider=provider.name,
                    model=attempt_model,
                    input_hash=input_hash,
                    latency_ms=latency_ms,
                    tokens_json=None,
                    status="error",
                    error_message=str(e),
                )

        raise last_error or RuntimeError("No LLM providers available")

    async def run_json(
        self,
        tenant_id: UUID,
        task: str,
        prompt_version: str,
        messages: list[dict],
        output_schema: type[BaseModel],
        model: str | None = None,
        thinking: bool = False,
    ) -> BaseModel:
        input_text = json.dumps(messages, sort_keys=True)
        input_hash = hashlib.sha256(input_text.encode()).hexdigest()[:16]

        last_error: Exception | None = None
        for provider in self.providers:
            attempt_start = time.monotonic()
            attempt_model = model or (
                provider.reasoning_model if thinking else provider.default_model
            )
            kwargs: dict[str, Any] = dict(
                model=attempt_model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            if thinking and provider.name == "openrouter":
                kwargs["extra_body"] = {"reasoning": {"enabled": True}}
            if thinking and provider.name == "gemini":
                kwargs["reasoning_effort"] = "low"

            try:
                response = await provider.client.chat.completions.create(**kwargs)
                latency_ms = int((time.monotonic() - attempt_start) * 1000)

                content = response.choices[0].message.content or "{}"
                parsed = json.loads(content)
                validated = output_schema(**parsed)

                tokens = None
                if response.usage:
                    tokens = {
                        "prompt": response.usage.prompt_tokens,
                        "completion": response.usage.completion_tokens,
                        "total": response.usage.total_tokens,
                    }

                self.last_provider = provider.name
                self.last_model = attempt_model
                await self._log_run(
                    tenant_id=tenant_id,
                    task=task,
                    prompt_version=prompt_version,
                    provider=provider.name,
                    model=attempt_model,
                    input_hash=input_hash,
                    latency_ms=latency_ms,
                    tokens_json=tokens,
                    status="success",
                )

                return validated

            except Exception as e:
                last_error = e
                latency_ms = int((time.monotonic() - attempt_start) * 1000)
                await self._log_run(
                    tenant_id=tenant_id,
                    task=task,
                    prompt_version=prompt_version,
                    provider=provider.name,
                    model=attempt_model,
                    input_hash=input_hash,
                    latency_ms=latency_ms,
                    tokens_json=None,
                    status="error",
                    error_message=str(e),
                )

        raise last_error or RuntimeError("No LLM providers available")

    async def _log_run(self, **kwargs: Any) -> None:
        try:
            async with async_session_factory() as session:
                run = LLMRun(
                    id=uuid.uuid4(),
                    tenant_id=kwargs["tenant_id"],
                    task=kwargs["task"],
                    provider=kwargs["provider"],
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
