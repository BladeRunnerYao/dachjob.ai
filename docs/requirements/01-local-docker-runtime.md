# Requirement 01: Local Docker Runtime

## Owner Agent

Infrastructure Agent

## Goal

Create a local Docker Compose environment that can run the MVP cheaply on a laptop. The only required external dependency is DeepSeek API.

## Services

| Service | Technology | Port | Purpose |
|---|---|---:|---|
| `frontend` | Next.js | 3000 | Dashboard UI |
| `api` | FastAPI + Uvicorn | 8000 | REST API |
| `worker` | Celery | none | Async jobs |
| `postgres` | pgvector Postgres 16 | 5432 | Data + embeddings |
| `redis` | Redis 7 | 6379 | Queue + cache |
| `minio` | MinIO | 9000, 9001 | Local object storage |
| `prometheus` | Prometheus | 9090 | Optional metrics |
| `grafana` | Grafana | 3001 | Optional dashboards |

## Required Files

- `infra/docker/docker-compose.yml`
- `infra/docker/prometheus.yml`
- `.env.example`
- `apps/api/Dockerfile`
- `apps/web/Dockerfile`
- root `README.md` local setup section

## Environment Variables

```env
APP_ENV=local
APP_NAME=dachjob.ai
SECRET_KEY=change-me-in-local-dev

DATABASE_URL=postgresql+psycopg://dachjob:dachjob@postgres:5432/dachjob
REDIS_URL=redis://redis:6379/0

DEEPSEEK_API_KEY=sk-your-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_FAST=deepseek-v4-flash
DEEPSEEK_MODEL_REASONING=deepseek-v4-pro

S3_ENDPOINT_URL=http://minio:9000
S3_ACCESS_KEY_ID=minioadmin
S3_SECRET_ACCESS_KEY=minioadmin
S3_BUCKET_NAME=dachjob-artifacts
```

## Docker Compose Requirements

1. `postgres` must use a pgvector-enabled image.
2. `minio` must create bucket `dachjob-artifacts`.
3. `api` and `worker` must share the same backend image.
4. `api` must mount source code for local reload.
5. `frontend` must use `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`.
6. Compose must define persistent volumes for Postgres, MinIO, and Grafana.

## Local Commands

```bash
cp .env.example .env
docker compose -f infra/docker/docker-compose.yml up --build
docker compose -f infra/docker/docker-compose.yml exec api alembic upgrade head
docker compose -f infra/docker/docker-compose.yml exec api python -m app.db.seed_demo
```

## Acceptance Criteria

- `http://localhost:3000` loads frontend.
- `http://localhost:8000/docs` loads FastAPI docs.
- `http://localhost:8000/api/health` returns `ok`.
- `http://localhost:9001` loads MinIO console.
- Postgres has extension `vector` enabled.
- Worker connects to Redis without errors.

## Implementation Plan

1. Create `infra/docker/docker-compose.yml`.
2. Create `.env.example`.
3. Create backend and frontend Dockerfiles.
4. Add health checks to Compose where practical.
5. Add README local startup instructions.
6. Add simple troubleshooting section for port conflicts.
