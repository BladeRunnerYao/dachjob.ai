import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.auth import is_rate_limit_exempt_route
from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler
from app.core.logging import configure_logging
from app.core.rate_limit import RateLimitMiddleware
from app.core.redis_client import cache, close_redis, init_app_redis
from app.core.request_logging import RequestLoggingMiddleware
from app.db.session import engine
from app.modules.auth.api_keys import router as api_keys_router
from app.modules.auth.routes import router as auth_router
from app.modules.background_tasks.routes import router as background_tasks_router
from app.modules.jobs.routes import router as jobs_router
from app.modules.llm_gateway.routes import router as llm_gateway_router
from app.modules.matching.routes import router as matching_router
from app.modules.profiles.routes import router as profiles_router
from app.modules.resumes.routes import artifact_router as resume_artifact_router
from app.modules.resumes.routes import router as resumes_router
from app.modules.tenants.routes import router as tenants_router
from app.modules.tracker.routes import router as tracker_router

configure_logging()
logger = logging.getLogger(__name__)

settings = get_settings()


def _load_version() -> dict:
    path = os.path.join(os.path.dirname(__file__), "..", "version.json")
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {"branch": "unknown", "commit": "unknown"}


VERSION = _load_version()


def _build_cors_origins() -> list[str]:
    if settings.cors_origins:
        return [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if settings.app_env == "production":
        return []
    return ["http://localhost:3000", "http://127.0.0.1:3000"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "api_startup | branch=%s commit=%s provider=%s redis_enabled=%s worker_enabled=%s worker_fallback_to_sync=%s",
        VERSION.get("branch"),
        VERSION.get("commit"),
        settings.llm_provider,
        settings.redis_enabled,
        settings.worker_enabled,
        settings.worker_fallback_to_sync,
    )
    async with engine.begin() as _conn:
        pass
    await init_app_redis()
    yield
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title="dachjob.ai API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_build_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    RateLimitMiddleware,
    max_requests=settings.rate_limit_requests,
    window_seconds=settings.rate_limit_window_seconds,
    redis_url=settings.redis_url if settings.redis_enabled else None,
    exempt_routes=is_rate_limit_exempt_route,
)

app.add_exception_handler(AppError, app_error_handler)

app.include_router(tenants_router)
app.include_router(profiles_router)
app.include_router(jobs_router)
app.include_router(matching_router)
app.include_router(resumes_router)
app.include_router(resume_artifact_router)
app.include_router(llm_gateway_router)
app.include_router(tracker_router)
app.include_router(auth_router)
app.include_router(api_keys_router)
app.include_router(background_tasks_router)


@app.get("/api/health")
async def health():
    redis_health = await cache.health_check()
    return {
        "status": "ok",
        "service": "dachjob.ai-api",
        "checks": {
            "database": "ok",
            **redis_health,
            "object_storage": "ok",
        },
    }


@app.get("/api/version")
async def version():
    provider_models = {
        "vertex_ai": (settings.vertex_ai_model_fast, settings.vertex_ai_model_reasoning),
        "gemini": (settings.gemini_model_fast, settings.gemini_model_reasoning),
        "deepseek": (settings.deepseek_model_fast, settings.deepseek_model_reasoning),
        "openrouter": (settings.openrouter_model_fast, settings.openrouter_model_reasoning),
    }
    model_fast, model_reasoning = provider_models.get(
        settings.llm_provider,
        (settings.vertex_ai_model_fast, settings.vertex_ai_model_reasoning),
    )
    return {
        "service": "dachjob.ai-api",
        "version": app.version,
        "git_branch": VERSION.get("branch"),
        "git_commit": VERSION.get("commit"),
        "llm_provider": settings.llm_provider,
        "llm_model_fast": model_fast,
        "llm_model_reasoning": model_reasoning,
        "worker_enabled": settings.worker_enabled,
        "worker_fallback_to_sync": settings.worker_fallback_to_sync,
    }
