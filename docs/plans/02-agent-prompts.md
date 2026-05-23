# dachjob.ai Coding Agent Prompts

Use these prompts to start multiple implementation agents. Each prompt intentionally limits scope so agents can work in parallel.

## Agent 0: Repository Bootstrap

```text
You are implementing the initial repository skeleton for dachjob.ai.

Read:
- docs/requirements/00-master-prd.md
- docs/plans/00-parallel-agent-plan.md

Task:
Create the base monorepo structure for a local-first AI job search platform:
- app/backend
- app/frontend
- infra/docker
- docs already exists, do not rewrite requirements

Backend stack:
FastAPI, SQLAlchemy, Alembic, Celery, Redis, Postgres/pgvector.

Frontend stack:
Next.js, React, TypeScript.

Do:
1. Create backend pyproject and minimal app.
2. Create frontend package and minimal app.
3. Create placeholder Dockerfiles.
4. Ensure repository can be understood by later agents.

Do not implement full business logic yet.
```

## Agent 1: Infrastructure

```text
You are the Infrastructure Agent for dachjob.ai.

Read:
- docs/requirements/00-master-prd.md
- docs/requirements/01-local-docker-runtime.md

Implement only:
- infra/docker/docker-compose.yml
- infra/docker/prometheus.yml
- .env.example
- Docker-related README updates
- backend/frontend Dockerfile fixes if required

Goal:
Make local Docker Compose run frontend, api, worker, postgres with pgvector, redis, minio, prometheus, and grafana.

Acceptance:
- docker-compose -f infra/docker/docker-compose.yml up -d --build works with cached builds by default
- API docs should be reachable on localhost:8000/docs once backend agent implements API
- MinIO console on localhost:9001
- Grafana on localhost:3001

Do not implement business API logic.
```

## Agent 2: Backend Foundation

```text
You are the Backend Foundation Agent for dachjob.ai.

Read:
- docs/requirements/00-master-prd.md
- docs/requirements/02-backend-api.md

Implement only:
- app/backend/app/main.py
- app/backend/app/core/*
- app/backend/app/db/session.py
- app/backend/app/workers/celery_app.py
- basic health router

Goal:
Create a clean FastAPI foundation with settings, tenant context, database session, Redis/Celery wiring, and /api/health.

Acceptance:
- uvicorn app.main:app starts
- /api/health returns JSON
- OpenAPI docs load
- tenant context dependency resolves default local tenant slug

Do not implement job matching, resume generation, or frontend.
```

## Agent 3: Data Model

```text
You are the Data Model Agent for dachjob.ai.

Read:
- docs/requirements/00-master-prd.md
- docs/requirements/03-data-model.md

Implement:
- SQLAlchemy models
- Alembic configuration
- initial migration
- seed_demo.py
- repository helpers that enforce tenant_id filtering

Goal:
Create all core tables for tenants, users, profiles, evidence chunks, job postings, match reports, resume artifacts, applications, and LLM runs.

Acceptance:
- alembic upgrade head works
- vector extension is enabled
- seed_demo.py creates local tenant and sample data
- every business table has tenant_id

Do not implement LLM calls or frontend.
```

## Agent 4: LLM Gateway

```text
You are the LLM Platform Agent for dachjob.ai.

Read:
- docs/requirements/00-master-prd.md
- docs/requirements/04-llm-gateway.md

Implement:
- app/backend/app/modules/llm_gateway/*
- DeepSeek provider using OpenAI-compatible SDK
- prompt loader
- Pydantic output schemas
- LLM run logging
- fake provider for tests

Goal:
Centralize all DeepSeek API calls. Business modules must call the gateway rather than the OpenAI SDK directly.

Acceptance:
- LLMGateway.run_json validates output schemas
- every call logs llm_runs
- fake provider works in unit tests
- DeepSeek integration test can run when DEEPSEEK_API_KEY is present

Do not implement job scoring or resume rendering except schemas needed by gateway tests.
```

## Agent 5: Job Matching

```text
You are the Job Matching Agent for dachjob.ai.

Read:
- docs/requirements/00-master-prd.md
- docs/requirements/05-job-matching.md

Implement:
- job creation/list/detail endpoints
- JD parsing task
- deterministic scoring engine
- match report creation
- fit explanation through LLM gateway

Goal:
The user can paste a JD, parse it, score it, and see reasons/gaps.

Acceptance:
- POST /api/jobs creates a job
- POST /api/jobs/{id}/parse parses JD
- POST /api/jobs/{id}/match creates match report
- score has all required dimensions
- recommendation is apply/maybe/skip

Do not implement CV PDF generation.
```

## Agent 6: RAG and Resume

```text
You are the RAG and Resume Agent for dachjob.ai.

Read:
- docs/requirements/00-master-prd.md
- docs/requirements/06-rag-resume-generation.md

Implement:
- CV upload endpoint
- evidence chunking
- embedding or keyword retrieval interface
- evidence retrieval endpoint
- tailored CV generation through LLM gateway
- HTML CV renderer
- Playwright PDF export
- MinIO artifact storage

Goal:
Generate evidence-grounded tailored CVs with provenance metadata.

Acceptance:
- POST /api/profile/cv creates evidence chunks
- GET /api/jobs/{id}/evidence returns relevant chunks
- POST /api/jobs/{id}/resume generates HTML/PDF artifact
- every generated bullet has source_chunk_ids

Do not implement frontend beyond API contracts.
```

## Agent 7: Frontend

```text
You are the Frontend Agent for dachjob.ai.

Read:
- docs/requirements/00-master-prd.md
- docs/requirements/07-frontend-dashboard.md

Implement:
- Next.js dashboard under app/frontend
- navigation layout
- dashboard page
- profile vault page
- jobs list and job detail pages
- tracker page
- LLM runs page
- API client layer with mock fallback

Goal:
Create a usable SaaS-style operational UI, not a landing page.

Acceptance:
- localhost:3000 opens dashboard
- user can navigate all pages
- pages work with mock data if backend is not ready
- real API integration is isolated in lib/api

Do not implement backend logic.
```

## Agent 8: Tracker and Autofill Demo

```text
You are the Tracker and Autofill Agent for dachjob.ai.

Read:
- docs/requirements/00-master-prd.md
- docs/requirements/08-tracker-autofill.md

Implement:
- application tracker endpoints
- application status validation
- mock application form
- autofill payload generator
- clear human-review warning

Goal:
Track job applications and demonstrate safe autofill without automatic submission.

Acceptance:
- GET/POST/PATCH /api/applications work
- tracker can link job, score, resume artifact, notes
- mock autofill form can be populated
- no code path submits applications automatically

Do not build a real Chrome Web Store extension in MVP.
```
