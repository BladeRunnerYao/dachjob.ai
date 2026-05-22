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
        self.client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
        self.settings = settings

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
        model = model or settings.deepseek_model_fast

        start = time.monotonic()
        input_text = json.dumps(messages, sort_keys=True)
        input_hash = hashlib.sha256(input_text.encode()).hexdigest()[:16]

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.3,
            )
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
                    provider="deepseek",
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
