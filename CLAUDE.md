# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (Python/FastAPI)
```bash
# Setup
cd app/backend && pip install -e ".[dev]"

# Run lint
ruff check .
ruff format --check .

# Auto-fix lint
ruff check --fix .

# Run tests (exclude live provider smoke tests)
pytest tests/ --ignore=tests/test_provider_smoke.py -v

# Run a single test
pytest tests/test_job_status_filters.py -v

# Run migrations
alembic -c app/db/migrations/alembic.ini upgrade head

# Auto-generate migration
alembic -c app/db/migrations/alembic.ini revision --autogenerate -m "description"

# Run pre-commit on all files
pre-commit run --all-files
```

### Frontend (Next.js/React)
```bash
# Setup
cd app/frontend && npm ci

# Dev server
npm run dev

# Build
npm run build

# Static export (output: "export" in next.config.ts)
npm run build  # outputs to out/

# Lint
npm run lint
```

### iOS (SwiftUI)
```bash
cd ios
xcodegen generate   # Generate .xcodeproj from project.yml
open DachJob.xcodeproj
```

### Docker
```bash
# Full stack (API, frontend, Postgres, Redis, MinIO)
docker compose -f infra/docker/docker-compose.yml up --build

# With Celery worker
docker compose -f infra/docker/docker-compose.yml --profile worker --profile redis up --build

# Sources for local URLs
source scripts/local-env.sh
```

### Terraform
```bash
terraform -chdir=infra/terraform/live/gcp/dev init -backend=false
terraform -chdir=infra/terraform/live/gcp/dev validate
```

## Project Architecture

Three-tier application: **Next.js frontend** → **FastAPI backend** → **PostgreSQL + Redis + Object Storage**, with AI-powered job matching and CV generation for the DACH tech market.

### Repository Layout
```
app/backend/           FastAPI API, Celery worker, DB models, Alembic migrations, tests
app/frontend/          Next.js 16 (App Router), React 19, Tailwind CSS 4, static export
ios/                   SwiftUI native iOS app (XcodeGen project)
infra/                 Docker Compose, deploy scripts, k8s manifests, Terraform (GCP/Azure/AWS)
docs/                  Requirements, deployment notes
scripts/               Local dev convenience scripts
samples/               Sample data
.github/workflows/     CI, multi-cloud deploy, admin tasks
```

### Backend Structure (app/backend/app/)
```
main.py                FastAPI app entry, middleware, router registration
core/                  Config, auth, security, rate limiting, Redis client, email, logging, telemetry
db/                    SQLAlchemy models, async session, Alembic migrations
modules/               Feature modules, each with routes + service layer:
  auth/                JWT auth, API keys, password reset
  jobs/                Job CRUD, URL import, source parsing, LLM extraction
  profiles/            Candidate profile CRUD, CV import (Markdown/URL/PDF)
  matching/            JD parsing (deterministic + LLM), skill taxonomy, match scoring
  resumes/             Tailored CV generation, HTML rendering (WeasyPrint PDF), storage
  llm_gateway/         Multi-provider LLM gateway with caching, observability, failover
  storage/             Unified object storage (GCS, Azure Blob, S3)
  tenants/             Multi-tenant management
  tracker/             Application tracking, autofill
  background_tasks/    Background task orchestration (sync or Celery)
workers/               Celery app config, async task definitions
```

### Frontend Structure (app/frontend/src/)
```
app/                   Next.js App Router pages (dashboard, jobs, profile, tracker, LLM runs, auth)
components/            Reusable UI components (sidebar, cards, modals, badges, dashboard widgets)
contexts/              React context (AuthContext with JWT token management)
lib/api/               API client layer: base-client.ts (fetch wrapper with auth), typed domain modules
```

### Key Architecture Decisions

- **LLM Gateway**: Provider-ordered failover (`vertex_ai` → `azure_openai` → `gemini` → `deepseek` → `openrouter`). Task-specific model tiers (fast/quality/reasoning). Response caching via Redis with SHA-256 input hashing. Every LLM call is logged to `llm_runs` table for observability.
- **Background Tasks**: Long-running operations (job import, matching, resume generation) run via Celery when `WORKER_ENABLED=true`, or synchronously in the API process via `worker_fallback_to_sync=true`. Background tasks are tracked in the `background_tasks` table with progress, status, and idempotency keys.
- **Config**: All settings via `pydantic-settings` from environment variables (no .env committed). Single `Settings` class at `app/backend/app/core/config.py`.
- **Database**: Async SQLAlchemy 2.0 with asyncpg driver. Async session factory injected via FastAPI dependency. Alembic for migrations. All models in `app/db/models.py` with UUID primary keys.
- **Object Storage**: Provider-agnostic via `STORAGE_PROVIDER` env var. Supports GCS, Azure Blob, S3-compatible (MinIO for local dev).
- **Multi-Cloud**: Same application abstractions across GCP (Cloud Run + GKE), Azure (Container Apps), AWS (ECS Fargate). Interchangeable storage, LLM, database, and cache backends per cloud.
- **Frontend**: Static export (`output: "export"`). API base URL determined at build-time via `NEXT_PUBLIC_API_BASE_URL`. For cloud deployments, this is empty (same-origin); for local dev, `http://localhost:8000`.
- **API Client**: Single `ApiClient` class (`app/frontend/src/lib/api/client.ts`) wrapping domain-specific API modules. Auto-redirects to `/login` on 401. Handles 202 (background task in progress) responses. Has mock fallbacks for development.

### Data Flow (Resume Generation)
1. Job imported → raw JD stored → LLM extracts structured requirements (skills, seniority, etc.)
2. Candidate profile uploaded (Markdown/URL/PDF) → LLM extracts structured profile
3. Match scores computed per requirement → gaps identified → explanation generated
4. Tailored resume generated via LLM → rendered as HTML → converted to PDF via WeasyPrint
5. Artifacts stored in object storage → protected behind JWT auth → linked in application tracker

### CI Workflow (ci.yml)
Three parallel job groups: backend (ruff + pytest), frontend (eslint + build), terraform (fmt + validate per cloud). A `validate` job gates by aggregating all results. Deploy workflows (`deploy-gcp.yml`, `deploy-azure.yml`, `deploy-aws.yml`) run independently.
