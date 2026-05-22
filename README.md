# dachjob.ai

`dachjob.ai` is a local-first, multi-tenant, multi-cloud-ready AI job search platform demo for the German/DACH market.

The product helps engineers evaluate AI Platform, Data Platform, MLOps, Backend Cloud, and Platform Engineering roles, then generate evidence-grounded tailored CVs using DeepSeek API.

This repository is intended to contain both:

- Requirements and implementation plans under `docs/`
- Project code under `apps/` and `infra/`

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
