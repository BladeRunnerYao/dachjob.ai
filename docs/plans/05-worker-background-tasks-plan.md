# Plan: Move Long-Running Workflows onto the Celery Worker

## Current Finding

Redis is already useful and should stay enabled. The Cloud Run API uses `REDIS_URL=redis://10.36.0.3:6379/0` for LLM caching, auth/API-key caching, tenant/profile/job caches, and rate limiting.

The Celery worker is also deployed and connected to the same Redis instance, but it currently only registers `app.workers.tasks.placeholder_task`. No production API path calls `.delay()`, `.apply_async()`, or `send_task()`, so the worker is alive but not doing product work.

## Goal

Keep the worker and make it the execution layer for long-running or retryable workflows:

- asynchronous job import and job description parsing
- asynchronous match computation
- asynchronous resume generation, evidence retrieval, and HTML/PDF artifact generation
- queued LLM-heavy workflows so provider limits are controlled
- email sending such as password reset email
- batch imports and future background sync jobs
- any workflow likely to exceed normal Cloud Run request latency

The API should become a fast command layer: validate authorization, create a background task record, enqueue Celery, and return `202 Accepted` with a task id. The worker should own the slow operation and update durable task status.

## Non-Goals

- Do not remove Redis caching.
- Do not remove synchronous read endpoints such as "get latest match" or "get latest resume".
- Do not put every small API request through Celery.
- Do not make `LLMGateway` always enqueue itself internally; that can deadlock when called from a worker. Queue workflows at the API/service boundary instead.
- Do not tear down GKE. This plan makes the existing worker useful.

## Target Architecture

API responsibilities:

- authenticate and authorize the request
- validate lightweight inputs
- create a `background_tasks` row
- enqueue a Celery task with ids only, not large payloads
- return `202` with task metadata
- expose task status/result endpoints for polling

Worker responsibilities:

- load tenant/user/job/profile ids from the task payload
- open its own async DB session
- execute existing service functions
- commit durable results such as `JobPosting.parsed_json`, `MatchReport`, `ResumeArtifact`, or email delivery status
- update task status, progress, result, and error metadata
- retry transient provider/network failures where safe

Redis responsibilities:

- remain API cache/rate-limit storage
- remain Celery broker/result backend
- optionally hold short-lived task locks/idempotency keys

## Implementation Steps

### 1. Add durable background task tracking

Add a new SQLAlchemy model in `app/backend/app/db/models.py`:

```python
class BackgroundTask(Base):
    __tablename__ = "background_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    kind = Column(String(80), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="queued", index=True)
    progress = Column(Integer, nullable=False, default=0)
    celery_task_id = Column(String(255), nullable=True, index=True)
    idempotency_key = Column(String(255), nullable=True, index=True)
    payload_json = Column(JSONB, nullable=False, default=dict)
    result_json = Column(JSONB, nullable=True)
    error_json = Column(JSONB, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
```

Create an Alembic migration:

- `background_tasks.id`
- indexes on `(tenant_id, status)`, `(tenant_id, kind)`, and `celery_task_id`
- optional unique index on `(tenant_id, idempotency_key)` where `idempotency_key is not null`

Allowed statuses:

- `queued`
- `running`
- `succeeded`
- `failed`
- `retrying`
- `cancelled`

### 2. Add task schemas, repository, and API endpoints

Add a new module:

- `app/backend/app/modules/background_tasks/schemas.py`
- `app/backend/app/modules/background_tasks/repository.py`
- `app/backend/app/modules/background_tasks/routes.py`
- `app/backend/app/modules/background_tasks/__init__.py`

Expose:

- `GET /api/tasks/{task_id}` returns one task for the authenticated tenant
- `GET /api/tasks?status=&kind=&limit=` lists recent tasks for the authenticated tenant
- optional `POST /api/tasks/{task_id}/cancel` marks queued tasks cancelled; do not try to kill running work in the first pass

Response shape:

```json
{
  "id": "uuid",
  "kind": "resume_generate",
  "status": "running",
  "progress": 40,
  "result": null,
  "error": null,
  "created_at": "...",
  "started_at": "...",
  "finished_at": null
}
```

Include the new router in `app/backend/app/main.py`.

### 3. Add a shared enqueue helper

Add `app/backend/app/modules/background_tasks/service.py`.

Responsibilities:

- create the `BackgroundTask` row
- build a minimal JSON payload with ids only
- call the Celery task using `.apply_async()`
- store `celery_task_id`
- flush/commit safely from the API route

Important:

- Do not pass ORM objects to Celery.
- Do not pass raw CV text, raw PDFs, or full job descriptions through Redis.
- Pass ids like `tenant_id`, `user_id`, `job_id`, `profile_id`, `application_id`, and let the worker read durable data from Postgres.

Example helper contract:

```python
async def enqueue_background_task(
    db: AsyncSession,
    *,
    tenant: TenantContext,
    kind: str,
    celery_task,
    payload: dict,
    idempotency_key: str | None = None,
) -> BackgroundTask:
    ...
```

### 4. Configure Celery for real queues

Edit `app/backend/app/workers/celery_app.py`:

- keep Redis broker/result backend
- add queue names and routing:

```python
celery_app.conf.task_routes = {
    "app.workers.tasks.import_jobs_task": {"queue": "jobs"},
    "app.workers.tasks.parse_job_task": {"queue": "jobs"},
    "app.workers.tasks.compute_match_task": {"queue": "jobs"},
    "app.workers.tasks.generate_resume_task": {"queue": "llm"},
    "app.workers.tasks.send_email_task": {"queue": "email"},
}
```

- add safer worker settings:

```python
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.task_acks_late = True
celery_app.conf.task_reject_on_worker_lost = True
celery_app.conf.task_time_limit = 15 * 60
celery_app.conf.task_soft_time_limit = 12 * 60
celery_app.conf.result_expires = 24 * 3600
```

Update the Kubernetes worker command in `infra/k8s/celery-worker/deployment.yaml` to consume the real queues:

```bash
celery -A app.workers.celery_app worker --loglevel=info --queues=jobs,llm,email,celery --uid=app --gid=app
```

Keep `placeholder_task` only as a smoke test, or rename it to `worker_smoke_task` so nobody mistakes it for product work.

### 5. Add worker task wrappers

Refactor `app/backend/app/workers/tasks.py` from placeholder-only to real task wrappers.

Celery tasks are synchronous functions, but the app services are async. Use a small wrapper:

```python
import asyncio

def run_async(coro):
    return asyncio.run(coro)
```

Each task should:

- load the `BackgroundTask` row
- skip if status is `cancelled`
- mark status `running`
- execute the async service
- update progress during major milestones
- store result ids in `result_json`
- mark status `succeeded`
- on exception, store a safe `error_json` and mark `failed`

Use `app.db.session.async_session_factory` inside the worker. Do not reuse API request sessions.

Recommended tasks:

```python
@celery_app.task(bind=True, autoretry_for=(httpx.HTTPError,), retry_backoff=True, retry_jitter=True, max_retries=3)
def import_jobs_task(self, background_task_id: str): ...

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=2)
def parse_job_task(self, background_task_id: str): ...

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=2)
def compute_match_task(self, background_task_id: str): ...

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=2)
def generate_resume_task(self, background_task_id: str): ...

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=3)
def send_email_task(self, background_task_id: str): ...
```

Use narrower retry exception types where possible. Do not retry validation errors like "job not found" or "profile not found".

### 6. Move job import and parsing to worker

Current synchronous entrypoint:

- `POST /api/jobs/import` in `app/backend/app/modules/jobs/routes.py`
- service: `app.modules.jobs.importer.import_job_urls`

Change default behavior:

- validate URL count and tenant
- create `BackgroundTask(kind="jobs_import")`
- enqueue `import_jobs_task`
- return `202 Accepted`

Task behavior:

- call `import_job_urls(db, tenant, urls)`
- for each imported job, ensure `parse_job_posting` runs
- invalidate `jobs:list` cache for the tenant
- store result:

```json
{
  "imported_job_ids": ["..."],
  "errors": [{"url": "...", "error": "..."}]
}
```

Optional compatibility:

- allow `?sync=true` for tests/admin use during the transition, but make async the normal UI path.

### 7. Move explicit parse and match actions to worker

Current synchronous entrypoints:

- `POST /api/jobs/{job_id}/parse`
- `POST /api/jobs/{job_id}/match`

Change:

- `parse` enqueues `parse_job_task` and returns task metadata
- `match` enqueues `compute_match_task` and returns task metadata
- keep `GET /api/jobs/{job_id}/match` as the read endpoint for latest completed match

Task behavior:

- `parse_job_task`: load job by `tenant_id/job_id`, call `parse_job_posting(db, tenant, job, force=True)`, invalidate `jobs:list`
- `compute_match_task`: load job/profile/evidence via `compute_match(db, tenant, job_id)`, invalidate `jobs:list`
- store `job_id`, `match_report_id`, `overall_score`, and `recommendation` in `result_json`

### 8. Move resume generation, RAG/evidence retrieval, and artifact generation to worker

Current synchronous entrypoint:

- `POST /api/jobs/{job_id}/resume`
- service: `app.modules.resumes.service.generate_resume`

Change:

- `POST /api/jobs/{job_id}/resume` enqueues `generate_resume_task` and returns `202`
- keep `GET /api/jobs/{job_id}/resume` as the latest completed resume read endpoint
- keep `/api/resumes/{artifact_id}/html` and `/api/resumes/{artifact_id}/pdf` unchanged

Task behavior:

- load tenant/user/job ids from payload
- call `generate_resume(db, tenant, job_id)`
- this already performs evidence retrieval, LLM resume generation, HTML generation, PDF generation, and storage upload
- store result:

```json
{
  "job_id": "...",
  "resume_artifact_id": "...",
  "html_object_key": "...",
  "pdf_object_key": "..."
}
```

Important:

- Make `generate_resume` idempotent enough for retries. If a retry creates duplicate artifacts, either accept duplicates for the first pass or add an idempotency key to reuse the latest artifact created by the same background task.
- Do not delete old artifacts automatically.

### 9. Queue LLM-heavy workflows at workflow boundaries

Keep `LLMGateway` as the internal provider abstraction and cache layer. Do not make `LLMGateway.run_text()` enqueue Celery tasks globally.

Instead, make these workflows execute in worker tasks:

- job import/parsing
- explicit job parsing
- match computation with LLM explanation
- resume generation
- profile URL/PDF extraction in a follow-up phase if it becomes slow

This keeps LLM calls queued without causing worker-to-worker recursion.

Add concurrency guidance:

- start with one worker replica and Celery concurrency `2-4` for LLM queues
- use `worker_prefetch_multiplier=1`
- consider a separate deployment for `llm` queue later if provider limits become the bottleneck

### 10. Move email sending to worker

Current password reset endpoint returns a reset link and does not call `send_reset_email`.

Change `POST /api/auth/forgot-password`:

- preserve the same public response message
- create a reset token and link when a password user exists
- enqueue `send_email_task` with the user id and a short email type such as `password_reset`
- do not reveal whether the email exists

Task behavior:

- load user/email from DB by id
- call `app.core.email.send_reset_email`
- store delivery result in `BackgroundTask.result_json`

Security:

- Do not put the reset token in task list responses.
- Either omit sensitive fields from `payload_json` responses or store email payload in `payload_json` but redact it in schemas.

### 11. Add frontend polling

Update frontend API types in `app/frontend/src/lib/api/types.ts` and client methods in `app/frontend/src/lib/api/client.ts`:

- `BackgroundTask`
- `TaskStatus`
- `getTask(taskId)`
- `listTasks(...)`

Update UI flows:

- job import should show queued/running/succeeded/failed states
- parse/match buttons should disable while task is running
- resume generation should show progress and then refetch latest resume/artifact when task succeeds
- failures should show a concise error message from `error_json.message`

Polling:

- poll every 2 seconds while status is `queued`, `running`, or `retrying`
- stop polling on `succeeded`, `failed`, or `cancelled`

### 12. Update deployment ordering and worker env

Update `.github/workflows/deploy.yml`:

- keep worker build/deploy in `target=all`; the worker is now useful
- ensure `deploy-worker` waits for API migrations when `target=all`, because worker code needs the new `background_tasks` table
- practical option: make `deploy-worker.needs` include `deploy-api`, and allow worker deploy only when `deploy-api` succeeded or was skipped because target is `worker`
- add `WORKER_ENABLED=true` to the worker Kubernetes env if a guard flag is introduced

Update `infra/k8s/celery-worker/deployment.yaml`:

- set queue command as described above
- consider reducing worker resources initially if idle cost matters
- keep Redis URL pointing to Memorystore

Optional later improvement:

- replace CPU-only HPA with queue-length scaling using KEDA, but do not block this implementation on KEDA.

### 13. Tests

Backend tests:

- add unit tests for `BackgroundTask` repository/service
- add API tests that async endpoints return `202` and a task id
- add tests that task status endpoints enforce tenant access
- add worker task tests with Celery eager mode or direct task function invocation
- test success and failure status updates for:
  - parse job
  - match job
  - resume generation
  - email task

Useful test config:

```python
celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True
```

Run:

```bash
cd app/backend
pytest tests/ --ignore=tests/test_provider_smoke.py -v
```

Frontend checks:

```bash
cd app/frontend
npm run lint
```

Deployment smoke checks:

```bash
kubectl logs -n celery-worker deploy/celery-worker -c worker --tail=100
kubectl exec -n celery-worker deploy/celery-worker -c worker -- celery -A app.workers.celery_app inspect registered
curl -fsS https://dachjob-dev-api-qxugiew36a-ew.a.run.app/api/health
```

### 14. Manual end-to-end validation

After deployment:

1. Import one job URL.
2. Confirm the API returns `202` with `kind=jobs_import`.
3. Poll `GET /api/tasks/{task_id}` until `succeeded`.
4. Confirm the imported job appears in the jobs list.
5. Trigger match generation and confirm the task succeeds.
6. Trigger resume generation and confirm the task succeeds.
7. Open the generated HTML/PDF artifact.
8. Check worker logs for the real tasks, not just `placeholder_task`.
9. Check Redis `llen celery` and queue behavior during a task burst.

## Acceptance Criteria

- The deployed worker registers real tasks for import, parse, match, resume, and email.
- The API no longer blocks on long import/parse/match/resume workflows by default.
- Long-running endpoints return `202 Accepted` with a durable task id.
- `GET /api/tasks/{id}` shows queued/running/succeeded/failed state.
- Existing read endpoints still return latest completed match/resume artifacts.
- Redis caching remains active for the API.
- Worker logs show real task execution under normal product flows.
- Tests cover task creation, task status access control, worker success, and worker failure.
