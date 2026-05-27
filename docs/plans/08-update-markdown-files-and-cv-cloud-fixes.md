# Plan: README Refresh and Cloud CV Generation Fixes

## Goals

1. Rewrite the root `README.md` into an industry-standard project README that reflects the current codebase, emphasizes multi-cloud deployment, and does not position the product around local-first or multi-tenant messaging.
2. Fix the Azure deployment issue where CV generation can return an example profile such as Jane Smith instead of the authenticated user's profile, such as Tiyao Li for `tiyao.li.@outlook.com`.
3. Fix the Google Cloud deployment flow where clicking Generate CV can show `Load failed` in the Tailored Resume panel.

## Working Approach

1. Inspect the current backend and frontend implementation for profile upload, profile lookup, authentication, resume generation, artifact retrieval, and cloud deployment configuration.
2. Identify where demo/mock data can be used in production paths and remove or gate it so authenticated cloud users only see their own persisted data.
3. Trace the Generate CV frontend request chain:
   - `POST /api/jobs/{job_id}/resume`
   - `GET /api/jobs/{job_id}/resume`
   - `GET /api/resumes/{artifact_id}/html`
   - `GET /api/resumes/{artifact_id}/pdf`
4. Fix backend or frontend issues that can produce a generic `Load failed`, especially missing auth headers on blob artifact requests, CORS/auth handling, storage retrieval, and production fallback behavior.
5. Update or add focused tests for the user/profile isolation and artifact loading behavior.
6. Run the relevant backend and frontend checks available in the repository.
7. Summarize root causes, code changes, and deployment notes for Azure and Google Cloud.

## Expected Files To Review

- `README.md`
- `app/backend/app/modules/profiles/*`
- `app/backend/app/modules/resumes/*`
- `app/backend/app/core/auth.py`
- `app/backend/app/db/models.py`
- `app/frontend/src/lib/api/*`
- `app/frontend/src/app/jobs/[id]/page.tsx`
- cloud/deployment files under `infra/`

## Acceptance Criteria

- `README.md` presents a polished overview, architecture, quickstart, configuration, deployment, and operations guide centered on multi-cloud AI job workflows.
- CV generation reads the authenticated user's candidate profile and never substitutes demo data in production.
- Resume artifact HTML/PDF fetches include the same authentication context as JSON API calls.
- GCP Generate CV failures surface useful errors and no longer fail because of unauthenticated artifact blob requests.
- Tests or static checks confirm the changed behavior.
