# dachjob.ai Parallel Agent Implementation Plan

## Purpose

This plan splits implementation so several coding agents can work in parallel without stepping on each other too much.

Each agent should read:

1. `docs/requirements/00-master-prd.md`
2. Its assigned requirement document
3. This plan

## Recommended Agent Assignments

| Agent | Doc | Main Paths | Dependencies |
|---|---|---|---|
| Infrastructure Agent | `01-local-docker-runtime.md` | `infra/docker/`, `.env.example`, Dockerfiles | none |
| Backend Foundation Agent | `02-backend-api.md` | `app/backend/app/core/`, `app/backend/app/main.py` | none |
| Data Model Agent | `03-data-model.md` | `app/backend/app/db/` | backend skeleton |
| LLM Platform Agent | `04-llm-gateway.md` | `app/backend/app/modules/llm_gateway/` | backend skeleton + data model for logging |
| Job Matching Agent | `05-job-matching.md` | `app/backend/app/modules/jobs/`, `matching/` | LLM gateway + data model |
| RAG/Resume Agent | `06-rag-resume-generation.md` | `profiles/`, `resumes/`, `storage/` | data model + LLM gateway |
| Frontend Agent | `07-frontend-dashboard.md` | `app/frontend/` | can start with mocks |
| Tracker/Autofill Agent | `08-tracker-autofill.md` | `tracker/`, frontend tracker pages | data model |

## Phase 0: Repository Bootstrap

Single agent should create:

- `app/backend`
- `app/frontend`
- `infra/docker`
- `pyproject.toml` for backend
- `package.json` for frontend
- initial README

After this, agents can split.

## Phase 1: Parallel Foundations

Can run in parallel:

- Infrastructure Agent creates Docker Compose.
- Backend Foundation Agent creates FastAPI skeleton.
- Frontend Agent creates Next.js skeleton with mock pages.
- Data Model Agent drafts SQLAlchemy models and migration.

Integration point:

- Compose must build API and web images.
- API health endpoint must run inside Compose.
- Frontend must call API base URL from env.

## Phase 2: Core AI Workflow

Can run in parallel after Phase 1:

- LLM Platform Agent builds DeepSeek gateway.
- Job Matching Agent builds job CRUD and scoring with fake parser first.
- RAG/Resume Agent builds CV upload, chunking, and storage.
- Tracker Agent builds application model endpoints.

Integration point:

- JD parsing uses LLM gateway.
- Matching uses parsed job plus evidence.
- Resume generation uses retrieved evidence plus LLM gateway.
- Tracker links job and resume artifact.

## Phase 3: End-to-End Demo

One integration agent should wire:

1. Upload CV.
2. Paste JD.
3. Parse JD.
4. Generate match.
5. Retrieve evidence.
6. Generate CV.
7. Save tracker record.
8. View LLM runs.

## Phase 4: Polish and Interview Pack

Create:

- Demo seed data
- Architecture diagram
- 2-minute demo script
- README screenshots
- Grafana dashboard or simple metrics page
- Terraform skeleton for Azure/AWS/GCP

## Coding Rules for Agents

- Do not auto-submit applications.
- Do not hardcode DeepSeek API key.
- Keep all business data tenant-scoped.
- Use Pydantic schemas for LLM outputs.
- Add tests for module-specific logic.
- Keep module boundaries clean.
- Prefer simple local-first implementation over premature microservices.

## Integration Test Scenario

Use this as the final shared acceptance test:

1. Run `docker-compose -f infra/docker/docker-compose.yml up -d --build`.
2. Run migrations.
3. Seed demo tenant and profile.
4. Create a job from sample JD.
5. Parse JD with DeepSeek.
6. Generate match report.
7. Generate tailored CV.
8. Confirm artifact stored in MinIO.
9. Confirm LLM runs logged.
10. Confirm tracker record visible in frontend.
