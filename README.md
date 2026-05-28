# dachjob.ai

AI-assisted job matching and CV generation for technical roles in the DACH market.

dachjob.ai imports job descriptions, extracts structured requirements, compares them with a candidate profile, and generates evidence-grounded tailored CV artifacts. The platform is designed to run across cloud providers with interchangeable infrastructure, storage, worker, and LLM backends.

## Features

- Job import from URLs or pasted job descriptions
- Structured requirement extraction for skills, seniority, location, and role metadata
- Candidate profile import from Markdown, URL content, or PDF resume upload
- Evidence chunking from candidate profiles for requirement-to-CV traceability
- Match scoring with explanations, gaps, and recommendations
- Tailored HTML and PDF CV generation
- Application tracker with generated resume links
- Background task execution for long-running imports, matching, and resume workflows
- LLM observability through persisted provider, model, latency, status, and error metadata
- Multi-cloud deployment paths for Google Cloud and Azure, with AWS-oriented abstractions in the application layer

## Architecture

```text
Next.js frontend
    |
FastAPI API
    |
Postgres + pgvector
    |
Redis + Celery worker
    |
Object storage for HTML/PDF artifacts
    |
LLM gateway: Vertex AI, Gemini API, Azure OpenAI, DeepSeek, OpenRouter
```

### Runtime Components

| Component | Implementation |
| --- | --- |
| Frontend | Next.js 16, React 19, Tailwind CSS |
| API | FastAPI, SQLAlchemy, Alembic |
| Worker | Celery with Redis broker/backend |
| Database | PostgreSQL 16 with pgvector |
| Artifact storage | GCS, Azure Blob Storage, or S3-compatible storage |
| Resume export | HTML rendering with WeasyPrint PDF generation |
| LLM access | Provider-ordered gateway with task-specific model tiers |
| Deployment | Docker, Cloud Run/GKE, Azure Container Apps, Terraform modules |

## Repository Layout

```text
app/backend/          FastAPI API, database models, migrations, workers, tests
app/frontend/         Next.js application
docs/                 Requirements, plans, and deployment notes
infra/deploy/         Cloud deployment and migration scripts
infra/docker/         Docker Compose runtime
infra/k8s/            Worker manifests
infra/terraform/      GCP and Azure infrastructure modules
scripts/              Developer convenience scripts
```

## Quickstart

### Prerequisites

- Docker and Docker Compose
- Python 3.12 for backend development
- Node.js 26 for frontend development
- At least one configured LLM provider key or cloud credential

### Run With Docker Compose

```bash
docker compose -f infra/docker/docker-compose.yml up --build
```

The default compose stack starts the API, frontend, Postgres, Redis, and MinIO. To print local URLs into your shell:

```bash
source scripts/local-env.sh
```

### Enable Worker Mode

```bash
docker compose -f infra/docker/docker-compose.yml --profile worker --profile redis up --build
```

Set `WORKER_ENABLED=true` when the API should enqueue long-running workflows to Celery. Leave it false to execute those workflows synchronously in the API process.

## Configuration

Core environment variables:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy database connection string |
| `JWT_SECRET` / `SECRET_KEY` | Auth and application signing secrets |
| `CORS_ORIGINS` | Comma-separated frontend origins allowed to call the API |
| `REDIS_URL` / `REDIS_ENABLED` | Redis cache, rate limiting, and worker coordination |
| `WORKER_ENABLED` | Switch between synchronous API execution and Celery background jobs |
| `STORAGE_PROVIDER` | `gcs`, `azure_blob`, or S3-compatible default |
| `STORAGE_BUCKET_NAME` | Artifact bucket/container name |
| `LLM_PROVIDER` | Preferred provider: `vertex_ai`, `gemini`, `azure_openai`, `deepseek`, or `openrouter` |
| `NEXT_PUBLIC_API_BASE_URL` | Browser-visible API URL for the frontend |
| `INTERNAL_API_BASE_URL` | Server-side API URL for frontend runtime calls |

Provider-specific variables include `VERTEX_AI_PROJECT_ID`, `GEMINI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, and `OPENROUTER_API_KEY`.

## Multi-Cloud Architecture

Every layer of the stack has been designed to run on either Google Cloud or Azure, with the same application code and interchangeable backends.

| Concern | Google Cloud | Azure |
| --- | --- | --- |
| **API compute** | Cloud Run (serverless) | Azure Container Apps |
| **Frontend compute** | Cloud Run (serverless) | Azure Container Apps |
| **Worker compute** | GKE Autopilot (Kubernetes) | Azure Container Apps |
| **Database** | Cloud SQL — PostgreSQL 16 + `pgvector` | PostgreSQL Flexible Server + `vector` extension |
| **Cache & broker** | Memorystore (Redis 7.0) | Azure Cache for Redis |
| **Object storage** | Cloud Storage (GCS) — S3-compatible | Azure Blob Storage |
| **Container registry** | Artifact Registry (Docker) | Azure Container Registry |
| **Secrets** | Secret Manager | Key Vault |
| **LLM inference** | Vertex AI · Gemini API | Azure OpenAI Service |
| **Monitoring & logging** | Cloud Monitoring · Cloud Logging | Application Insights · Log Analytics |
| **Networking** | VPC · Serverless VPC Connector | Virtual Network · Private DNS Zones |
| **IAM / workload identity** | Service Accounts · Workload Identity Federation | Managed Identity · Azure AD OIDC |
| **Database migrations** | Cloud Run Jobs | Azure Container Apps Jobs |
| **Terraform state** | Cloud Storage bucket | Azure Storage container |

The application layer uses the same abstractions regardless of provider: `STORAGE_PROVIDER` selects between GCS, Azure Blob, or S3-compatible storage, and the LLM gateway transparently fails over across Vertex AI, Gemini, Azure OpenAI, DeepSeek, and OpenRouter.

## Cloud Deployment

### Google Cloud

The GCP path deploys:

- FastAPI API on Cloud Run
- Next.js frontend on Cloud Run
- Postgres on Cloud SQL
- Redis on Memorystore
- Resume artifacts in Cloud Storage
- Celery worker on GKE
- Images in Artifact Registry

Primary entry points:

```bash
infra/deploy/scripts/deploy-gcp.sh all <api-image> <frontend-image> <worker-image>
infra/deploy/scripts/run-migrations-gcp.sh <api-image>
```

### Azure

The Azure path deploys:

- API, frontend, and worker on Azure Container Apps
- PostgreSQL Flexible Server
- Azure Cache for Redis
- Resume artifacts in Azure Blob Storage
- Images in Azure Container Registry
- Secrets through Azure Key Vault and Container Apps secrets

Primary entry points:

```bash
infra/deploy/scripts/deploy-azure.sh all <api-image> <frontend-image> <worker-image>
infra/deploy/scripts/run-migrations-azure.sh <api-image>
```

## Development

Backend:

```bash
cd app/backend
pip install -e ".[dev]"
pytest tests/ --ignore=tests/test_provider_smoke.py -v
```

Frontend:

```bash
cd app/frontend
npm ci
npm run lint
npm run build
```

Live provider smoke tests are available when credentials are configured:

```bash
cd app/backend
pytest tests/test_provider_smoke.py -v
```

## Documentation

- [Master PRD](docs/requirements/00-master-prd.md)
- [RAG Resume Generation](docs/requirements/06-rag-resume-generation.md)
- [GCP Architecture](docs/deployment/gcp-architecture.md)
- [Terraform Guide](infra/terraform/README.md)
- [Documentation Index](docs/index.html)

## Operating Notes

- Generated CVs must be grounded in stored candidate evidence.
- Resume HTML/PDF artifacts are protected API resources and require the authenticated user's bearer token.
- The platform prepares job materials; users remain responsible for review and submission.
