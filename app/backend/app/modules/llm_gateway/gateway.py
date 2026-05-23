import hashlib
import json
import time
import uuid
from typing import Any
from uuid import UUID

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.config import get_settings
from app.db.models import LLMRun
from app.db.session import async_session_factory


class LLMGateway:
    def __init__(self):
        settings = get_settings()
        if settings.openrouter_api_key:
            self.client = AsyncOpenAI(
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
            )
            self.default_model = settings.openrouter_model_fast
            self.default_model_reasoning = settings.openrouter_model_reasoning
            self.provider = "openrouter"
        else:
            deepseek_key = getattr(settings, 'deepseek_api_key', '') or ''
            if not deepseek_key:
                raise RuntimeError(
                    "No LLM API key configured. "
                    "Set OPENROUTER_API_KEY (or uncomment DEEPSEEK_API_KEY) in .env"
                )
            self.client = AsyncOpenAI(
                api_key=deepseek_key,
                base_url=getattr(settings, 'deepseek_base_url', 'https://api.deepseek.com') or 'https://api.deepseek.com',
            )
            self.default_model = getattr(settings, 'deepseek_model_fast', 'deepseek-v4-flash') or 'deepseek-v4-flash'
            self.default_model_reasoning = getattr(settings, 'deepseek_model_reasoning', 'deepseek-v4-pro') or 'deepseek-v4-pro'
            self.provider = "deepseek"
        self.settings = settings

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
        settings = self.settings
        model = model or self.default_model

        start = time.monotonic()
        input_text = json.dumps(messages, sort_keys=True)
        input_hash = hashlib.sha256(input_text.encode()).hexdigest()[:16]

        try:
            kwargs: dict[str, Any] = dict(
                model=model,
                messages=messages,
                temperature=0.3,
            )
            if reasoning:
                kwargs["extra_body"] = {"reasoning": {"enabled": True}}
            if response_format:
                kwargs["response_format"] = response_format

            response = await self.client.chat.completions.create(**kwargs)
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
                prompt_version=prompt_version,
                model=model,
                input_hash=input_hash,
                latency_ms=latency_ms,
                tokens_json=tokens,
                status="success",
            )

            return content

        except Exception as e:
            latency_ms = int((time.monotonic() - start) * 1000)
            await self._log_run(
                tenant_id=tenant_id,
                task=task,
                prompt_version=prompt_version,
                model=model,
                input_hash=input_hash,
                latency_ms=latency_ms,
                tokens_json=None,
                status="error",
                error_message=str(e),
            )
            raise

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
        settings = self.settings
        model = model or self.default_model

        start = time.monotonic()
        input_text = json.dumps(messages, sort_keys=True)
        input_hash = hashlib.sha256(input_text.encode()).hexdigest()[:16]

        try:
            kwargs: dict[str, Any] = dict(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            if thinking:
                kwargs["extra_body"] = {"reasoning": {"enabled": True}}

            response = await self.client.chat.completions.create(**kwargs)
            latency_ms = int((time.monotonic() - start) * 1000)

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

            await self._log_run(
                tenant_id=tenant_id,
                task=task,
                prompt_version=prompt_version,
                model=model,
                input_hash=input_hash,
                latency_ms=latency_ms,
                tokens_json=tokens,
                status="success",
            )

            return validated

        except Exception as e:
            latency_ms = int((time.monotonic() - start) * 1000)
            await self._log_run(
                tenant_id=tenant_id,
                task=task,
                prompt_version=prompt_version,
                model=model,
                input_hash=input_hash,
                latency_ms=latency_ms,
                tokens_json=None,
                status="error",
                error_message=str(e),
            )
            raise

    async def _log_run(self, **kwargs: Any) -> None:
        try:
            async with async_session_factory() as session:
                run = LLMRun(
                    id=uuid.uuid4(),
                    tenant_id=kwargs["tenant_id"],
                    task=kwargs["task"],
                    provider=self.provider,
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
