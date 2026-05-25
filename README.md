# dachjob.ai

`dachjob.ai` is a local-first, multi-tenant, multi-cloud-ready AI job search platform demo for the German/DACH market.

The product helps engineers evaluate AI Platform, Data Platform, MLOps, Backend Cloud, and Platform Engineering roles, then generate evidence-grounded tailored CVs using DeepSeek API.

This repository is intended to contain both:

- Requirements and implementation plans under `docs/`
- Project code under `app/` and `infra/`

## Documentation

Start here:

- [Master PRD](docs/requirements/00-master-prd.md)
- [Parallel Agent Implementation Plan](docs/plans/00-parallel-agent-plan.md)
- [HTML Documentation Index](docs/index.html)

## MVP Stack

- Backend: Python, FastAPI, SQLAlchemy, Alembic
- Worker: Celery, Redis
- Database: Postgres 16 with pgvector
- Object storage: MinIO locally, S3-compatible adapter first
- LLM: DeepSeek API through OpenAI-compatible SDK
- Frontend: Next.js / React
- PDF: HTML CV template exported with Playwright
- Local runtime: Docker Compose

## Local-First Principle

The first version should run fully on a local machine with Docker Compose. The only external dependency is the DeepSeek API key.

The project should not automatically submit job applications. It may prepare forms, CVs, cover notes, and answers, but the user must review and submit manually.

## Local URLs

After the Docker Compose stack is running, source the local environment helper to export the ports and print clickable URLs:

```bash
source scripts/local-env.sh
```

It exports `DACHJOB_WEB_URL`, `DACHJOB_JOBS_URL`, `DACHJOB_API_URL`, `DACHJOB_API_HEALTH_URL`, `DACHJOB_API_DOCS_URL`, and MinIO URLs for quick testing from VS Code terminals.

## Local Docker Convention

Use `docker-compose` with `infra/docker/docker-compose.yml` for local builds and runs. The default path should preserve Docker's build cache:

```bash
docker-compose -f infra/docker/docker-compose.yml up -d --build
```

Only add `--no-cache` when explicitly requested.

The local image and container names are:

- API: `dachjob-backend-api`
- Worker: `dachjob-backend-worker` (behind `--profile worker`)
- Frontend: `dachjob-frontend`

## Worker Mode

The application supports two runtime modes controlled by `WORKER_ENABLED`:

- **`WORKER_ENABLED=false`** (default): No worker dependency. API routes execute workflows synchronously.
  - Run with: `docker compose up`
  - Redis is still used for caching and rate limiting.

- **`WORKER_ENABLED=true`**: API routes enqueue long-running workflows to Celery. The worker executes them asynchronously.
  - Run with: `docker compose --profile worker --profile redis up`
  - Requires Redis and worker containers.

### Local Docker Setup

Default local command runs API/frontend/postgres/redis/minio without worker:

```bash
docker compose -f infra/docker/docker-compose.yml up
```

To run with worker:

```bash
docker compose -f infra/docker/docker-compose.yml --profile worker --profile redis up
```
