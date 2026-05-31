# Copilot Instructions

## Merge Rules

1. **Never merge until all CI jobs pass.** Wait for all build, deploy, and smoke-test jobs (deploy-gcp.yml, deploy-azure.yml, deploy-aws.yml) to complete — not just the Validate step. Never use `--admin` to bypass required status checks.
2. **Never merge without explicit permission.** Present the PR link and wait for the user to request a merge.
3. **Monitor CI and fix failures.** After pushing, watch all three workflow runs. Deploy failures on main are your responsibility.

## Workflow

- Use `git worktree` for changes — create a feature branch from main in a separate worktree, make changes there, then PR back to main.
- **Run pre-commit before testing.** Always run `pre-commit run --all-files` before running tests or pushing. Fix all findings before proceeding.
- Changes to CI workflows, Terraform, or deployment scripts may affect all three clouds (GCP, Azure, AWS).
- Deploy workflows currently use the dev Terraform roots even though workflow inputs expose `staging` and `prod`. Treat staging/prod as requiring separate backend state, GitHub Environments, variables, and secrets before production use.

## Build & Test Commands

### Backend (Python 3.12 — FastAPI)

```bash
cd app/backend
pip install -e ".[dev]"

# Lint
ruff check .
ruff format --check .

# Run all tests (excludes live provider tests)
pytest tests/ --ignore=tests/test_provider_smoke.py -v

# Run a single test
pytest tests/test_auth_security.py -v
pytest tests/test_auth_security.py::test_function_name -v

# Live provider smoke tests (requires credentials)
pytest tests/test_provider_smoke.py -v
```

### Frontend (Node.js 26 — Next.js 16 / React 19)

```bash
cd app/frontend
npm ci
npm run lint
npm run build
```

### Database Migrations (Alembic)

```bash
cd app/backend

# Create a new migration
alembic -c app/db/migrations/alembic.ini revision --autogenerate -m "description"

# Run migrations
alembic -c app/db/migrations/alembic.ini upgrade head
```

Migration files live in `app/backend/app/db/migrations/versions/` and follow sequential numbering (`0001_`, `0002_`, etc.).

### Docker Compose (full stack)

```bash
docker compose -f infra/docker/docker-compose.yml up --build
# With worker:
docker compose -f infra/docker/docker-compose.yml --profile worker --profile redis up --build
```

Source `scripts/local-env.sh` to export convenience variables (`DACHJOB_API_URL`, `DACHJOB_WEB_URL`, etc.) for local shells.

### iOS App (Swift 6.2 / SwiftUI)

```bash
cd ios
xcodegen generate   # requires: brew install xcodegen
open DachJob.xcodeproj
# Build & run with ⌘R in Xcode (requires Xcode 26+, iOS 26.0+ target)
```

## Architecture

```
Next.js frontend → FastAPI API → PostgreSQL 16 (pgvector)
                                → Redis + Celery worker
                                → Object storage (GCS / Azure Blob / S3)
                                → LLM gateway (Vertex AI, Gemini, Azure OpenAI, DeepSeek, OpenRouter)

iOS (SwiftUI)    → same FastAPI API (JWT auth, same endpoints)
```

### Backend Module Structure

Each domain module lives in `app/backend/app/modules/<name>/` with a consistent shape:
- `routes.py` — FastAPI router (always prefixed `/api/<name>`)
- `schemas.py` — Pydantic request/response models
- `repository.py` — SQLAlchemy database queries
- `service.py` — Business logic (when non-trivial)

Modules: `auth`, `jobs`, `profiles`, `matching`, `resumes`, `tracker`, `llm_gateway`, `background_tasks`, `storage`, `tenants`.

Some modules have been split into sub-files:
- `jobs/`: `import_service.py` (URL import flow), `source_parsers.py` (per-source scraping), `fetcher.py`, `extractor.py`
- `matching/parser/`: `deterministic.py`, `llm.py`, `skills.py` — called from `jd_parser.py`
- `resumes/`: `prompt_builder.py`, `renderer_html.py`, `renderer_pdf.py`, `artifacts.py` — orchestrated by `service.py`

### Key Patterns

**Multi-tenancy**: All API routes receive a `TenantContext` via `get_tenant_context` dependency (`app.core.tenant`). Tenant is resolved from the JWT bearer token (authenticated routes) or the default tenant slug (public routes).

**Background tasks**: Long-running workflows use `run_or_enqueue()` (`app.modules.background_tasks.execution`) which either dispatches to Celery (when `WORKER_ENABLED=true`) or runs synchronously in the API process. Always provide both `celery_task` and `sync_runner` arguments. Set `WORKER_ENABLED=false` for local dev without Redis/Celery.

**LLM gateway**: Uses the OpenAI client library against multiple backends. Tasks declare a model tier (`fast`, `quality`, `reasoning`) in `TASK_MODEL_TIERS` (`app.modules.llm_gateway.gateway`) and the gateway resolves the actual model per provider. Persists every call as an `LLMRun` row for observability.

**Redis caching**: The `cache` singleton (`app.core.redis_client`) provides `get_json`/`set_json`/`delete_pattern`. Route handlers invalidate cache on writes. Gracefully degrades when Redis is unavailable.

**Error handling**: Raise `AppError(code, message, details, status_code)` from `app.core.errors` for all expected API errors. It is serialized as `{"error": {"code": ..., "message": ..., "details": ...}}`. Do not raise raw `HTTPException` for domain errors.

**Logging**: Structured JSON via `app.core.logging`. Use `logger.info("event_name | key=value key2=value2 ...")` style (space-separated key=value pairs, not f-strings with interpolated dicts).

**Configuration**: All settings use `pydantic-settings` (`app.core.config.Settings`), loaded from environment variables or a `.env` file. Access via `get_settings()` (LRU-cached singleton).

### Frontend

- App Router (Next.js 16), Tailwind CSS v4, React 19
- **Important**: This uses Next.js 16 which has breaking changes from earlier versions. Read docs in `node_modules/next/dist/docs/` before writing code.
- API client is split by domain in `src/lib/api/`: `jobs.ts`, `resumes.ts`, `profiles.ts`, `matching.ts`, `applications.ts`, `tasks.ts`, `llm-runs.ts`. All call through `base-client.ts` → `request()`.
- `base-client.ts` handles: auth headers (localStorage JWT token), API base URL resolution, automatic redirect to `/login` on 401, and HTTP 202 (background task enqueued) as a success response.
- Auth state via React Context (`src/contexts/AuthContext.tsx`).

### iOS App

- Native SwiftUI app in `ios/`, connects to the same API as the web frontend.
- Token stored in Keychain (not UserDefaults). `APIClient.swift` attaches `Authorization: Bearer` headers.
- Default API server is the AWS CloudFront endpoint. User can override via Settings screen on login page.
- Smoke-test jobs are filtered client-side by title regex.

## Code Style

**Backend**: Ruff with `line-length = 100`, `target-version = "py312"`. Rules: E, F, I, W (ignores E501). Pre-commit runs ruff check + format. Migrations in `app/db/migrations/` are excluded from ruff.

**Frontend**: ESLint with `eslint-config-next` (core-web-vitals + TypeScript).

## Multi-Cloud Deployment

| Layer | GCP | Azure | AWS |
|---|---|---|---|
| API/Frontend | Cloud Run | Container Apps | ECS Fargate (ALB) |
| Worker | GKE Autopilot | Container Apps | ECS Fargate |
| Database | Cloud SQL (PG 16) | PostgreSQL Flexible | RDS PostgreSQL (pgvector) |
| Cache | Memorystore | Azure Cache for Redis | ElastiCache |
| Storage | GCS | Blob Storage | S3 |
| Secrets | Secret Manager | Key Vault | Secrets Manager |
| Registry | Artifact Registry | ACR | ECR |
| CI Auth | Workload Identity Federation | Azure AD OIDC | IAM OIDC |
| IaC | `infra/terraform/live/gcp/dev` (GCS state) | `infra/terraform/live/azure/dev` (Azure Storage) | `infra/terraform/live/aws/dev` (S3 + DynamoDB) |

### Environment Model

| Cloud | Terraform root | Deploy workflow | Active environment |
|---|---|---|---|
| GCP | `infra/terraform/live/gcp/dev/` | `deploy-gcp.yml` | dev |
| Azure | `infra/terraform/live/azure/dev/` | `deploy-azure.yml` | dev |
| AWS | `infra/terraform/live/aws/dev/` | `deploy-aws.yml` | dev |

`staging` and `prod` Terraform roots exist under each cloud but are not wired to CI variables/secrets yet.

### AWS Details

- **Account ID**: `755545427549` | **Region**: `eu-west-1` | **Cluster**: `dachjob-dev-cluster`
- **Auth**: `export AWS_PROFILE=dachjob-admin` (AdministratorAccess)
- **Terraform state**: S3 bucket `dachjob-dev-terraform-state`, DynamoDB lock `dachjob-dev-terraform-lock`

| Service | URL / Host |
|---|---|
| CloudFront (HTTPS) | `https://d3ktpumdo7sly4.cloudfront.net` |
| ALB (HTTP) | `dachjob-dev-alb-1730467011.eu-west-1.elb.amazonaws.com` |
| API health | `https://d3ktpumdo7sly4.cloudfront.net/api/health` |
| RDS | `dachjob-dev-postgres-b682.cfsmow8y4er3.eu-west-1.rds.amazonaws.com:5432` |
| ElastiCache | `dachjob-dev-redis.k1t1ty.0001.euw1.cache.amazonaws.com:6379` |

ECS services: `dachjob-dev-api` (count 1), `dachjob-dev-frontend` (count 1), `dachjob-dev-worker` (count 0, disabled).

**Password reset** — via workflow dispatch (`reset_password_for` input) or manually:
```bash
curl -sS -X POST "${API_URL}/api/auth/forgot-password" \
  -H "Content-Type: application/json" -d '{"email":"user@example.com"}'
# Extract token from reset_link, then:
curl -sS -X POST "${API_URL}/api/auth/reset-password" \
  -H "Content-Type: application/json" -d '{"token":"...","new_password":"NewPass123!"}'
```

### Azure Deployment Note

Azure OIDC federation sometimes fails transiently (`No subscriptions found` during `az login`). The deploy workflow already includes retry logic.
