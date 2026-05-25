# Plan: Worker-Optional Background Workflows and Operational Logging

## Current Finding

Redis is already useful and should stay enabled. The Cloud Run API uses `REDIS_URL=redis://10.36.0.3:6379/0` for LLM caching, auth/API-key caching, tenant/profile/job caches, and rate limiting.

The Celery worker is also deployed and connected to the same Redis instance, but it currently only registers `app.workers.tasks.placeholder_task`. No production API path calls `.delay()`, `.apply_async()`, or `send_task()`, so the worker is alive but not doing product work.

## New Requirements

The application must support two runtime modes:

- `WORKER_ENABLED=false`: no worker dependency. API routes execute workflows synchronously, as they mostly do today. The service must work without Kubernetes worker pods.
- `WORKER_ENABLED=true`: API routes enqueue long-running workflows to Celery. The worker executes them asynchronously and the frontend polls task status.

Deployment must also support both modes:

- Worker-disabled deploy: deploy API/frontend only, set `WORKER_ENABLED=false`, skip worker image build/deploy, and optionally scale any existing GKE worker deployment to zero.
- Worker-enabled deploy: deploy API/frontend plus the GKE worker, set `WORKER_ENABLED=true`, and ensure migrations run before worker rollout.

Logging must be upgraded:

- logs should be structured enough for debugging and operations
- errors should include request/task correlation ids
- error and critical logs should also be written to a local error-log folder for future agent analysis

## Goal

Keep the worker, make it optional, and make it useful when enabled.

Long-running or retryable workflows should support both execution modes:

- asynchronous job import and job description parsing
- asynchronous match computation
- asynchronous resume generation, evidence retrieval, and HTML/PDF artifact generation
- queued LLM-heavy workflows so provider limits are controlled
- email sending such as password reset email
- batch imports and future background sync jobs
- any workflow likely to exceed normal Cloud Run request latency

When `WORKER_ENABLED=false`, these workflows must still work synchronously so the product can run without Kubernetes cost.

When `WORKER_ENABLED=true`, the API should become a fast command layer: validate authorization, create a background task record, enqueue Celery, and return `202 Accepted` with a task id. The worker should own the slow operation and update durable task status.

## Non-Goals

- Do not remove Redis caching.
- Do not make Redis optional as part of this plan.
- Do not remove synchronous execution paths. They are required for `WORKER_ENABLED=false`.
- Do not make `LLMGateway` always enqueue itself internally. That can deadlock when called from a worker. Queue workflows at the API/service boundary instead.
- Do not automatically destroy the GKE cluster in the first implementation. Scaling worker workloads to zero is safe; full infrastructure teardown should be an explicit later step.

## Runtime Modes

### Worker Disabled

Configuration:

```env
WORKER_ENABLED=false
```

Behavior:

- API routes call service functions directly.
- No Celery task is required for product functionality.
- Existing response shapes should be preserved where practical.
- Background task rows may still be created for audit/logging, but the route should return the actual synchronous result unless the frontend has already been updated to accept task responses.
- Cloud Run API health should remain green as long as DB, Redis, and storage are healthy.

Expected use cases:

- low-cost deploy
- local development
- small traffic
- demo mode where current synchronous performance is acceptable

### Worker Enabled

Configuration:

```env
WORKER_ENABLED=true
```

Behavior:

- API routes create `background_tasks` rows and enqueue Celery tasks.
- Long-running routes return `202 Accepted` with task metadata.
- Frontend polls `GET /api/tasks/{task_id}`.
- Worker performs long workflows and updates task status/result/error.

Expected use cases:

- batch imports
- longer LLM workflows
- resume/PDF generation
- better retry and queue control
- avoiding Cloud Run request timeout pressure

## Target Architecture

API responsibilities:

- authenticate and authorize the request
- validate lightweight inputs
- decide execution mode from `settings.worker_enabled`
- if worker disabled, run the service inline and return the normal result
- if worker enabled, create a `background_tasks` row, enqueue Celery, and return `202`
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
- remain Celery broker/result backend when worker mode is enabled
- optionally hold short-lived task locks/idempotency keys

Logging responsibilities:

- stdout/stderr remains the primary log stream for Cloud Logging
- JSON or key-value structured logs include correlation ids and safe operational context
- error/critical logs are copied into `ERROR_LOG_DIR` as JSONL files

## Implementation Steps

### 1. Add worker runtime config

Edit `app/backend/app/core/config.py`.

Add:

```python
worker_enabled: bool = False
worker_fallback_to_sync: bool = True
worker_enqueue_timeout_seconds: float = 2.0
log_level: str = "INFO"
log_json: bool = True
error_log_to_file: bool = True
error_log_dir: str = "/tmp/dachjob-error-logs"
```

Rules:

- `redis_enabled` stays `True` by default.
- `worker_enabled` defaults to `False` to avoid a Kubernetes dependency by default.
- `worker_fallback_to_sync` controls what happens when `WORKER_ENABLED=true` but enqueue fails.
- For production worker-enabled deploys, consider `WORKER_FALLBACK_TO_SYNC=false` after the worker is stable, so queue failures are visible.
- Add `worker_enabled` and `worker_fallback_to_sync` to `/api/version` in `app/backend/app/main.py` so frontend and operators can see runtime mode.

### 2. Add durable background task tracking

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

### 3. Add task schemas, repository, and API endpoints

Add a new module:

- `app/backend/app/modules/background_tasks/schemas.py`
- `app/backend/app/modules/background_tasks/repository.py`
- `app/backend/app/modules/background_tasks/service.py`
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

Security:

- never return sensitive payload fields such as reset tokens
- enforce tenant access on every task read
- include `user_id` filtering when appropriate

Include the new router in `app/backend/app/main.py`.

### 4. Add a dual-mode workflow helper

Add `app/backend/app/modules/background_tasks/execution.py`.

This module should centralize the worker-enabled vs worker-disabled decision so routes do not duplicate logic.

Recommended API:

```python
async def run_or_enqueue(
    db: AsyncSession,
    *,
    tenant: TenantContext,
    kind: str,
    payload: dict,
    celery_task,
    sync_runner: Callable[[], Awaitable[Any]],
    result_serializer: Callable[[Any], dict] | None = None,
    idempotency_key: str | None = None,
) -> tuple[str, Any]:
    ...
```

Return contract:

- `("sync", result)` when `WORKER_ENABLED=false` or fallback-to-sync is used
- `("queued", background_task)` when `WORKER_ENABLED=true` and enqueue succeeds

Responsibilities:

- create a `BackgroundTask` row for both modes when useful
- build a minimal JSON payload with ids only
- call Celery `.apply_async()` only when `settings.worker_enabled` is true
- store `celery_task_id`
- if enqueue fails:
  - log the error with `worker_enabled=true`
  - if `worker_fallback_to_sync=true`, run `sync_runner`
  - otherwise raise an operational error such as `worker_enqueue_failed`
- do not pass ORM objects to Celery
- do not pass raw CV text, raw PDFs, or full job descriptions through Redis

Route behavior:

- when mode is `sync`, return the existing response model/result
- when mode is `queued`, return `202 Accepted` with `BackgroundTaskResponse`

### 5. Configure Celery for real queues

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

### 6. Add worker task wrappers

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
- log start/success/failure with task ids and domain ids

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

### 7. Move job import and parsing to dual-mode execution

Current synchronous entrypoint:

- `POST /api/jobs/import` in `app/backend/app/modules/jobs/routes.py`
- service: `app.modules.jobs.importer.import_job_urls`

Change behavior:

- validate URL count and tenant
- call `run_or_enqueue(...)`
- if `WORKER_ENABLED=false`, run `import_job_urls` inline and return existing `JobImportResponse`
- if `WORKER_ENABLED=true`, create `BackgroundTask(kind="jobs_import")`, enqueue `import_jobs_task`, and return `202 Accepted`

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

### 8. Move explicit parse and match actions to dual-mode execution

Current synchronous entrypoints:

- `POST /api/jobs/{job_id}/parse`
- `POST /api/jobs/{job_id}/match`

Change behavior:

- if `WORKER_ENABLED=false`, keep current synchronous behavior and response models
- if `WORKER_ENABLED=true`, enqueue and return `202 Accepted`
- keep `GET /api/jobs/{job_id}/match` as the read endpoint for latest completed match

Task behavior:

- `parse_job_task`: load job by `tenant_id/job_id`, call `parse_job_posting(db, tenant, job, force=True)`, invalidate `jobs:list`
- `compute_match_task`: load job/profile/evidence via `compute_match(db, tenant, job_id)`, invalidate `jobs:list`
- store `job_id`, `match_report_id`, `overall_score`, and `recommendation` in `result_json`

### 9. Move resume generation, RAG/evidence retrieval, and artifact generation to dual-mode execution

Current synchronous entrypoint:

- `POST /api/jobs/{job_id}/resume`
- service: `app.modules.resumes.service.generate_resume`

Change behavior:

- if `WORKER_ENABLED=false`, call `generate_resume(db, tenant, job_id)` inline and return existing `ResumeResponse`
- if `WORKER_ENABLED=true`, enqueue `generate_resume_task` and return `202 Accepted`
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

### 10. Queue LLM-heavy workflows at workflow boundaries

Keep `LLMGateway` as the internal provider abstraction and cache layer. Do not make `LLMGateway.run_text()` enqueue Celery tasks globally.

Instead, make these workflows dual-mode at the API/service boundary:

- job import/parsing
- explicit job parsing
- match computation with LLM explanation
- resume generation
- profile URL/PDF extraction in a follow-up phase if it becomes slow

This keeps LLM calls queued when worker mode is enabled without causing worker-to-worker recursion.

Add concurrency guidance:

- start with one worker replica and Celery concurrency `2-4` for LLM queues
- use `worker_prefetch_multiplier=1`
- consider a separate deployment for `llm` queue later if provider limits become the bottleneck

### 11. Move email sending to dual-mode execution

Current password reset endpoint returns a reset link and does not call `send_reset_email`.

Change `POST /api/auth/forgot-password`:

- preserve the same public response message
- create a reset token and link when a password user exists
- if `WORKER_ENABLED=false`, call `send_reset_email` inline after token creation
- if `WORKER_ENABLED=true`, enqueue `send_email_task`
- do not reveal whether the email exists

Task behavior:

- load user/email from DB by id
- call `app.core.email.send_reset_email`
- store delivery result in `BackgroundTask.result_json`

Security:

- Do not put the reset token in task list responses.
- Either omit sensitive fields from `payload_json` responses or store email payload in `payload_json` but redact it in schemas.
- Never log raw reset tokens.

### 12. Add frontend support for both modes

Update frontend API types in `app/frontend/src/lib/api/types.ts` and client methods in `app/frontend/src/lib/api/client.ts`:

- `BackgroundTask`
- `TaskStatus`
- `getTask(taskId)`
- `listTasks(...)`
- dual response handling for long-running endpoints

Frontend behavior:

- call `/api/version` once after login or app boot and store `worker_enabled`
- when an endpoint returns `202`, show queued/running/succeeded/failed state and poll
- when an endpoint returns the existing synchronous result, keep the current behavior
- job import should work in both modes
- parse/match buttons should disable while task is running in worker mode
- resume generation should show progress in worker mode and then refetch latest resume/artifact when task succeeds
- failures should show a concise error message from `error_json.message`

Polling:

- poll every 2 seconds while status is `queued`, `running`, or `retrying`
- stop polling on `succeeded`, `failed`, or `cancelled`

### 13. Update deployment workflow for worker-enabled and worker-disabled deploys

Edit `.github/workflows/deploy.yml`.

Add a `workflow_dispatch` input:

```yaml
worker_mode:
  description: Worker mode for this deploy
  required: true
  type: choice
  default: disabled
  options:
    - disabled
    - enabled
```

Add an optional input:

```yaml
scale_down_worker_when_disabled:
  description: Scale existing GKE worker deployment to zero when worker mode is disabled
  required: false
  type: boolean
  default: true
```

Prepare job rules:

- `worker_mode=disabled` sets `WORKER_ENABLED=false`
- `worker_mode=enabled` sets `WORKER_ENABLED=true`
- `deploy_worker=true` only when:
  - target is `all` or `worker`
  - and `worker_mode=enabled`
- `target=worker` with `worker_mode=disabled` should fail fast with a clear workflow error

API deploy:

- include `WORKER_ENABLED=${WORKER_ENABLED}` in `gcloud run deploy --set-env-vars`
- include `WORKER_FALLBACK_TO_SYNC=true` initially
- include logging env vars:

```env
LOG_LEVEL=INFO
LOG_JSON=true
ERROR_LOG_TO_FILE=true
ERROR_LOG_DIR=/tmp/dachjob-error-logs
```

Worker deploy:

- only build and deploy worker when `worker_mode=enabled`
- ensure `deploy-worker` waits for API migrations when `target=all`, because worker code needs the `background_tasks` table
- practical option: make `deploy-worker.needs` include `deploy-api`, and allow worker deploy only when `deploy-api` succeeded or when target is exactly `worker` and migrations are known to be current
- set `WORKER_ENABLED=true` in the worker Kubernetes manifest

Worker-disabled deploy:

- skip `build-worker`
- skip `deploy-worker`
- if `scale_down_worker_when_disabled=true`, add a job that:
  - gets GKE credentials
  - deletes or scales down the HPA first
  - scales `deployment/celery-worker` to `0`

Use this sequence because the current HPA has `minReplicas: 1` and can recreate the pod:

```bash
kubectl delete hpa celery-worker --namespace="${GKE_NAMESPACE}" --ignore-not-found
kubectl scale deployment/celery-worker --namespace="${GKE_NAMESPACE}" --replicas=0
kubectl get deploy,hpa,pods --namespace="${GKE_NAMESPACE}" -o wide
```

Worker-enabled deploy should re-apply `infra/k8s/celery-worker/deployment.yaml`, which recreates the HPA and deployment replicas.

Local Docker Compose:

- edit `infra/docker/docker-compose.yml`
- keep API service runnable with `WORKER_ENABLED=false`
- put the `worker` service behind `profiles: ["worker"]`
- set `WORKER_ENABLED=true` only inside the worker service
- default local command should run API/frontend/postgres/redis/minio without worker
- explicit worker local command should be documented as:

```bash
docker compose --profile worker --profile redis up
```

### 14. Keep Terraform safe

Do not destroy GKE automatically in this implementation.

Reason: `infra/terraform/main.tf` currently creates the GKE cluster unconditionally. Adding a default-disabled `count` around the GKE module could plan deletion of the existing cluster on the next Terraform apply.

For this implementation:

- deploy mode controls whether worker pods run
- worker-disabled mode scales the worker deployment to zero
- GKE cluster teardown remains a separate, explicit infrastructure cleanup

Add a follow-up note to `infra/terraform/README.md`:

- if cost remains too high even with zero worker pods, implement a separate `enable_worker_infrastructure` variable
- guard all `module.gke` outputs with `try(...)`
- update GitHub Actions so `worker_mode=enabled` requires GKE infrastructure
- run a separate reviewed Terraform plan before destroying the cluster

### 15. Add structured application logging

Add `app/backend/app/core/logging.py`.

Required functions:

```python
def configure_logging() -> None:
    ...

def get_logger(name: str) -> logging.Logger:
    ...

def record_error_log(message: str, *, exc: BaseException | None = None, **context: Any) -> None:
    ...
```

`configure_logging()` should:

- configure root/app log level from `settings.log_level`
- write normal logs to stdout/stderr so Cloud Run and GKE keep receiving logs
- support JSON logs when `LOG_JSON=true`
- install an error archive handler when `ERROR_LOG_TO_FILE=true`

`record_error_log(...)` should:

- log to a dedicated logger such as `app.errors`
- include `exc_info` when an exception is provided
- include safe context fields such as `tenant_id`, `user_id`, `job_id`, `task_id`, `celery_task_id`, `request_id`, `path`, and `operation`
- never log secrets, API keys, JWTs, reset tokens, raw CV content, or full prompts

Call `configure_logging()` from:

- `app/backend/app/main.py` before app startup logs
- `app/backend/app/workers/celery_app.py` before worker startup logs
- migration jobs only if safe and not noisy

### 16. Archive error logs into a folder

Implement an `ErrorArchiveHandler` in `app/backend/app/core/logging.py`.

Behavior:

- handles `ERROR` and `CRITICAL` records
- creates `settings.error_log_dir` if missing
- writes JSON Lines files under:

```text
{ERROR_LOG_DIR}/YYYY-MM-DD/errors.jsonl
```

Each line should include:

```json
{
  "timestamp": "...",
  "level": "ERROR",
  "logger": "app.modules.matching.service",
  "message": "...",
  "exception_type": "ValueError",
  "exception_message": "...",
  "traceback": "...",
  "request_id": "...",
  "tenant_id": "...",
  "user_id": "...",
  "background_task_id": "...",
  "celery_task_id": "...",
  "operation": "resume_generate"
}
```

Operational note:

- Cloud Run and GKE container filesystems are ephemeral.
- This folder is still useful for local/dev and short-lived in-container agent debugging.
- Long-term retention should use Cloud Logging sinks or a future GCS error-log exporter.
- Do not block requests if file writing fails. The handler should catch file I/O errors and fall back to stderr.

Add tests for:

- error archive directory creation
- JSONL line written for an error
- exception traceback included
- sensitive context fields redacted or omitted

### 17. Add request and task correlation ids

Add request logging middleware, for example `app/backend/app/core/request_logging.py`.

Behavior:

- read `X-Request-ID` if provided, otherwise generate a UUID
- store request id in a `contextvars.ContextVar`
- add `X-Request-ID` to every response
- log request start/end with method, path, status, duration_ms, tenant_id when available
- log unhandled exceptions with request context

Add Celery task context:

- use Celery signals such as `task_prerun`, `task_postrun`, and `task_failure`
- set context vars for `celery_task_id`, `background_task_id`, and task name
- include them in every worker log line

### 18. Fix existing logger usage and add operational logs

Audit current logging:

- replace `logging.getLogger("uvicorn")` in app code with `logging.getLogger(__name__)` or `get_logger(__name__)`
- avoid logger names that hide the source module
- keep `uvicorn` logger for uvicorn internals only
- use `logger.exception(...)` only inside exception handlers
- use `logger.warning(...)` for recoverable fallback paths
- use `logger.info(...)` for task lifecycle and deploy/runtime mode events

Add logs at these points:

- API startup: branch, commit, provider, redis_enabled, worker_enabled, worker_fallback_to_sync
- Redis init: enabled, connected, disabled, fallback
- background task created: task id, kind, tenant id, user id
- Celery enqueue success/failure: background task id, celery task id, queue
- synchronous fallback used: reason and operation
- worker task start/progress/success/failure
- LLM call start/end: provider, model, task, status, latency_ms, cache_hit, no prompt text
- storage upload/download failures: bucket/key, no document contents
- email send success/failure: email type and user id, not reset token
- auth failures at warning level only when operationally useful, without tokens

### 19. Documentation updates

Update:

- `README.md`
- `infra/terraform/README.md`
- `docs/deployment/gcp-architecture.md`
- local Docker docs if they mention worker as always-on

Docs should explain:

- Redis stays enabled for API caching in both modes
- `WORKER_ENABLED=false` means API executes workflows directly and no worker pod is required
- `WORKER_ENABLED=true` means long workflows are queued to Celery
- GitHub Actions `worker_mode` controls whether worker is deployed
- worker-disabled deploy can scale the existing GKE worker deployment to zero
- error logs are available in `ERROR_LOG_DIR` as JSONL for local/agent analysis

### 20. Tests

Backend tests:

- settings parse `WORKER_ENABLED=true/false`
- `/api/version` reports worker mode
- async endpoints run synchronously when `WORKER_ENABLED=false`
- async endpoints return `202` and task id when `WORKER_ENABLED=true`
- enqueue failure falls back to sync when `WORKER_FALLBACK_TO_SYNC=true`
- enqueue failure returns operational error when fallback is false
- task status endpoints enforce tenant access
- worker task success and failure update status correctly
- error archive handler writes JSONL files
- request id appears in logs and response headers

Useful Celery eager test config:

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

Deployment smoke checks for worker-disabled mode:

```bash
curl -fsS https://dachjob-dev-api-qxugiew36a-ew.a.run.app/api/version
curl -fsS https://dachjob-dev-api-qxugiew36a-ew.a.run.app/api/health
kubectl get deploy,hpa,pods -n celery-worker || true
```

Expected:

- API reports `worker_enabled=false`
- API health remains ok
- no running `celery-worker-*` pod if scale-down was requested

Deployment smoke checks for worker-enabled mode:

```bash
kubectl logs -n celery-worker deploy/celery-worker -c worker --tail=100
kubectl exec -n celery-worker deploy/celery-worker -c worker -- celery -A app.workers.celery_app inspect registered
curl -fsS https://dachjob-dev-api-qxugiew36a-ew.a.run.app/api/version
```

Expected:

- API reports `worker_enabled=true`
- worker registers real tasks for jobs, match, resume, and email
- logs include worker startup and queue names

### 21. Manual end-to-end validation

Worker-disabled deploy:

1. Deploy with `worker_mode=disabled`.
2. Confirm `/api/version` says `worker_enabled=false`.
3. Import one job URL.
4. Confirm the request completes synchronously and the job appears in the jobs list.
5. Trigger match generation and confirm the route returns the match result.
6. Trigger resume generation and confirm the route returns the resume artifact.
7. Confirm no worker pod is running if scale-down was enabled.
8. Confirm error logs still write to `ERROR_LOG_DIR` when a controlled test error is triggered locally.

Worker-enabled deploy:

1. Deploy with `worker_mode=enabled`.
2. Confirm `/api/version` says `worker_enabled=true`.
3. Import one job URL.
4. Confirm the API returns `202` with `kind=jobs_import`.
5. Poll `GET /api/tasks/{task_id}` until `succeeded`.
6. Confirm the imported job appears in the jobs list.
7. Trigger match generation and confirm the task succeeds.
8. Trigger resume generation and confirm the task succeeds.
9. Open the generated HTML/PDF artifact.
10. Check worker logs for the real tasks, not just `placeholder_task`.
11. Check Redis queue behavior during a task burst.

## Acceptance Criteria

- `WORKER_ENABLED=false` is the default.
- With `WORKER_ENABLED=false`, API/frontend product workflows still work without worker pods.
- With `WORKER_ENABLED=true`, long-running workflows enqueue to Celery and return durable task ids.
- GitHub Actions can deploy worker-disabled and worker-enabled modes.
- Worker-disabled deploy does not build/deploy worker and can scale the existing worker deployment to zero.
- Worker-enabled deploy restores worker deployment, queues, and HPA.
- The deployed worker registers real tasks for import, parse, match, resume, and email.
- Redis caching remains active for the API in both modes.
- Logs include request/task correlation ids and operational lifecycle events.
- Error and critical logs are archived to `ERROR_LOG_DIR` as JSONL without leaking secrets.
- Tests cover both worker modes, task status access control, worker success/failure, and error log archiving.
