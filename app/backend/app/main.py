import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.auth import is_rate_limit_exempt_route
from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler
from app.core.rate_limit import RateLimitMiddleware
from app.db.session import engine
from app.modules.auth.api_keys import router as api_keys_router
from app.modules.auth.routes import router as auth_router
from app.modules.jobs.routes import router as jobs_router
from app.modules.llm_gateway.routes import router as llm_gateway_router
from app.modules.matching.routes import router as matching_router
from app.modules.profiles.routes import router as profiles_router
from app.modules.resumes.routes import artifact_router as resume_artifact_router
from app.modules.resumes.routes import router as resumes_router
from app.modules.tenants.routes import router as tenants_router
from app.modules.tracker.routes import router as tracker_router

logger = logging.getLogger("uvicorn")

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
        "dachjob.ai API starting | branch=%s commit=%s provider=%s",
        VERSION.get("branch"),
        VERSION.get("commit"),
        settings.llm_provider,
    )
    async with engine.begin() as _conn:
        pass
    yield
    await engine.dispose()


app = FastAPI(
    title="dachjob.ai API",
    version="0.1.0",
    lifespan=lifespan,
)

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
    redis_url=settings.redis_url,
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


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "dachjob.ai-api",
        "checks": {
            "database": "ok",
            "redis": "ok",
            "object_storage": "ok",
        },
    }


@app.get("/api/version")
async def version():
    return {
        "service": "dachjob.ai-api",
        "version": app.version,
        "git_branch": VERSION.get("branch"),
        "git_commit": VERSION.get("commit"),
        "llm_provider": settings.llm_provider,
        "llm_model_fast": settings.gemini_model_fast,
        "llm_model_reasoning": settings.gemini_model_reasoning,
    }
