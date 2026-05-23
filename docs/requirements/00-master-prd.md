# dachjob.ai Master PRD

## Product Name

`dachjob.ai`

Working domain idea: `dachjob.ai`. The domain does not need to exist for the MVP.

## One-Sentence Pitch

`dachjob.ai` is a local-first AI job search platform for DACH-market technical roles that evaluates job fit, maps requirements to real candidate evidence, generates tailored DACH-style CVs, and tracks applications with LLM observability and human approval.

## Target Roles

The product is designed around job seekers targeting:

- AI Platform Engineer
- Data Platform Engineer
- MLOps Engineer
- Backend Cloud Engineer
- Platform Engineer
- AI Infrastructure Engineer
- DevOps / Systems Engineer

## Product Goals

1. Help users decide which DACH jobs are worth applying to.
2. Generate tailored CVs grounded only in real user evidence.
3. Demonstrate production-style AI platform architecture, not just LLM prompt usage.
4. Run locally with Docker Compose for cheap, private development.
5. Be multi-tenant and multi-cloud-ready by design, even if the first MVP only runs locally.

## Non-Goals

- Do not auto-submit applications.
- Do not scrape large job boards in MVP.
- Do not deploy to AKS/EKS/GKE in MVP.
- Do not build a payment system.
- Do not implement enterprise SSO in MVP.
- Do not invent candidate achievements or metrics.

## MVP User Flow

1. User opens the local dashboard.
2. User selects or creates a tenant.
3. User uploads or pastes a CV in Markdown.
4. System chunks the CV into evidence records and generates embeddings.
5. User pastes a DACH job description.
6. DeepSeek parses the job into structured requirements.
7. System computes deterministic match score.
8. DeepSeek produces a fit explanation based on the score and evidence.
9. System retrieves relevant CV evidence for the role.
10. DeepSeek generates a tailored CV draft using only retrieved evidence.
11. User previews HTML CV and exports PDF.
12. Application tracker saves job, score, status, notes, and artifacts.

## Architecture Summary

Use a modular monolith for MVP:

- One FastAPI backend
- One Celery worker
- One Postgres database with pgvector
- One Redis queue
- One MinIO object store
- One Next.js frontend
- One DeepSeek API integration through a centralized LLM gateway

This keeps the implementation realistic but manageable for local development.

## Core Modules

| Module | Requirement Doc | Can Be Built In Parallel |
|---|---|---|
| Local runtime and Docker | `01-local-docker-runtime.md` | Yes |
| Backend/API foundation | `02-backend-api.md` | Yes |
| Database and tenant model | `03-data-model.md` | Yes, after backend skeleton |
| LLM gateway and DeepSeek | `04-llm-gateway.md` | Yes |
| Job ingestion and matching | `05-job-matching.md` | Yes, after data model draft |
| RAG evidence and CV generation | `06-rag-resume-generation.md` | Yes, after profile/evidence model |
| Frontend dashboard | `07-frontend-dashboard.md` | Yes, with mocked API first |
| Tracker and autofill demo | `08-tracker-autofill.md` | Yes, after job/application model |

## Success Criteria

- `docker-compose -f infra/docker/docker-compose.yml up -d --build` starts all MVP services using cached builds by default.
- `/api/health` reports API, database, Redis, and MinIO status.
- User can upload CV Markdown.
- User can create a job from pasted JD text.
- JD parsing returns structured JSON.
- Match report includes overall score, score breakdown, reasons, and gaps.
- Tailored CV HTML and PDF are generated.
- Generated CV bullets include source evidence IDs in backend metadata.
- LLM runs are logged with model, task, tenant, status, and latency.
- Application tracker stores status and artifacts.

## Ethical Requirement

`dachjob.ai` must optimize for high-quality applications, not spam.

The system must never click Submit or Send on behalf of the user. The final application decision must remain with the user.

## Coding Agent Guidance

Each coding agent should read this master PRD plus its assigned module doc. Agents should avoid changing files outside their assigned area unless explicitly needed for integration.

When in doubt:

- Prefer local-first implementation.
- Prefer simple but production-shaped architecture.
- Prefer deterministic logic where possible and LLM explanation where useful.
- Keep tenant isolation visible in code and database schema.
- Keep user data and API keys private.
