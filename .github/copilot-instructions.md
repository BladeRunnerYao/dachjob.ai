# Copilot Instructions

## Merge Rules

1. **Never merge until all CI jobs pass.** Wait for all build, deploy, and smoke-test jobs (deploy-gcp.yml, deploy-azure.yml, deploy-aws.yml) to complete — not just the Validate step. Never use `--admin` to bypass required status checks.
2. **Never merge without explicit permission.** Present the PR link and wait for the user to request a merge.
3. **Monitor CI and fix failures.** After pushing, watch all three workflow runs. Deploy failures on main are your responsibility.

## Workflow

- Use `git worktree` for changes — create a feature branch from main in a separate worktree, make changes there, then PR back to main.
- Changes to CI workflows, Terraform, or deployment scripts may affect all three clouds (GCP, Azure, AWS).

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

## Architecture

```
Next.js frontend → FastAPI API → PostgreSQL 16 (pgvector)
                                → Redis + Celery worker
                                → Object storage (GCS / Azure Blob / S3)
                                → LLM gateway (Vertex AI, Gemini, Azure OpenAI, DeepSeek, OpenRouter)
```

### Backend Module Structure

Each domain module lives in `app/backend/app/modules/<name>/` with a consistent shape:
- `routes.py` — FastAPI router (always prefixed `/api/<name>`)
- `schemas.py` — Pydantic request/response models
- `repository.py` — SQLAlchemy database queries
- `service.py` — Business logic (when non-trivial)

Modules: `auth`, `jobs`, `profiles`, `matching`, `resumes`, `tracker`, `llm_gateway`, `background_tasks`, `storage`, `tenants`.

### Key Patterns

**Multi-tenancy**: All API routes receive a `TenantContext` via `get_tenant_context` dependency (`app.core.tenant`). Tenant is resolved from the JWT bearer token (authenticated routes) or the default tenant slug (public routes).

**Background tasks**: Long-running workflows use `run_or_enqueue()` (`app.modules.background_tasks.execution`) which either dispatches to Celery (when `WORKER_ENABLED=true`) or runs synchronously in the API process. Set `WORKER_ENABLED=false` for local dev without Redis/Celery.

**LLM gateway**: Uses the OpenAI client library against multiple backends. Tasks declare a model tier (`fast`, `quality`, `reasoning`) in `TASK_MODEL_TIERS` (`app.modules.llm_gateway.gateway`) and the gateway resolves the actual model per provider. Persists every call as an `LLMRun` row for observability.

**Redis caching**: The `cache` singleton (`app.core.redis_client`) provides `get_json`/`set_json`/`delete_pattern`. Route handlers invalidate cache on writes. Gracefully degrades when Redis is unavailable.

**Configuration**: All settings use `pydantic-settings` (`app.core.config.Settings`), loaded from environment variables or a `.env` file. Access via `get_settings()` (LRU-cached singleton).

### Frontend

- App Router (Next.js 16), Tailwind CSS v4, React 19
- API client in `src/lib/api/` — `base-client.ts` handles auth headers (localStorage JWT) and API base URL resolution
- Auth state via React Context (`src/contexts/AuthContext.tsx`)
- **Important**: This uses Next.js 16 which has breaking changes from earlier versions. Read docs in `node_modules/next/dist/docs/` before writing code.

## Code Style

**Backend**: Ruff with `line-length = 100`, `target-version = "py312"`. Rules: E, F, I, W (ignores E501). Pre-commit runs ruff check + format.

**Frontend**: ESLint with `eslint-config-next` (core-web-vitals + TypeScript).

## Multi-Cloud Deployment

| Layer | GCP | Azure | AWS |
|---|---|---|---|
| API/Frontend | Cloud Run | Container Apps | ECS Fargate (ALB) |
| Worker | GKE Autopilot | Container Apps | ECS Fargate |
| Database | Cloud SQL (PG 16) | PostgreSQL Flexible | RDS PostgreSQL |
| Cache | Memorystore | Azure Cache for Redis | ElastiCache |
| Storage | GCS | Blob Storage | S3 |
| Secrets | Secret Manager | Key Vault | Secrets Manager |
| Registry | Artifact Registry | ACR | ECR |
| CI Auth | Workload Identity Federation | Azure AD OIDC | IAM OIDC |
| IaC | `infra/terraform/live/gcp/dev` (GCS state) | `infra/terraform/live/azure/dev` (Azure Storage) | `infra/terraform/live/aws/dev` (S3 + DynamoDB) |

### AWS Details

- **Account ID**: `755545427549` | **Region**: `eu-west-1` | **Cluster**: `dachjob-dev-cluster`
- **Auth**: `export AWS_PROFILE=dachjob-admin` (AdministratorAccess)
- **API**: `https://d3ktpumdo7sly4.cloudfront.net/api/health`
- **Frontend**: `https://d3ktpumdo7sly4.cloudfront.net`
- **Terraform**: `infra/terraform/live/aws/dev/` (state in S3 `dachjob-dev-terraform-state`, lock in DynamoDB `dachjob-dev-terraform-lock`)

### Terraform Roots

- **GCP dev**: `infra/terraform/live/gcp/dev/`
- **Azure dev**: `infra/terraform/live/azure/dev/`
- **AWS dev**: `infra/terraform/live/aws/dev/`

### Azure Deployment Note

Azure OIDC federation sometimes fails transiently (`No subscriptions found` during `az login`). The deploy workflow already includes retry logic.
