from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler
from app.db.session import engine
from app.modules.tenants.routes import router as tenants_router
from app.modules.profiles.routes import router as profiles_router
from app.modules.jobs.routes import router as jobs_router
from app.modules.matching.routes import router as matching_router
from app.modules.resumes.routes import router as resumes_router
from app.modules.resumes.routes import artifact_router as resume_artifact_router
from app.modules.llm_gateway.routes import router as llm_gateway_router
from app.modules.tracker.routes import router as tracker_router
from app.modules.auth.routes import router as auth_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
