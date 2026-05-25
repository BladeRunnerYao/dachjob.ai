# Plan: Disable the Unused Celery Worker by Default

## Current Finding

Redis caching is already active and should stay active. It is used by the FastAPI backend running on Cloud Run, not by a Kubernetes API pod. The deployed API service `dachjob-dev-api` has `REDIS_URL=redis://10.36.0.3:6379/0`, and the backend uses `app.core.redis_client.cache` for LLM response caching, auth/API-key caching, tenant/profile/job caches, and rate limiting.

The GKE worker pod is different. It runs a Celery worker in the `celery-worker` namespace and connects to the same Memorystore Redis instance as a Celery broker/result backend. However, the current code only registers `app.workers.tasks.placeholder_task`, and the repository has no production caller using `.delay()`, `.apply_async()`, or `send_task()`. The worker is therefore deployed but not part of the product request path.

## Goal

Make the Celery worker opt-in and disabled by default, while keeping Redis enabled for the API.

The final implementation should:

- Keep `REDIS_ENABLED=true` and `REDIS_URL` for the Cloud Run API.
- Add an application-level worker config flag with a disabled default.
- Stop local Docker Compose from starting the worker unless explicitly requested.
- Stop GitHub Actions from building or deploying the worker when `target=all` unless an explicit deployment flag enables it.
- Provide a safe way to deactivate the currently running GKE worker resources.
- Preserve the existing worker code and Kubernetes manifest for future opt-in use.

## Non-Goals

- Do not remove Redis, Memorystore, or API Redis caching.
- Do not remove Celery dependencies or worker source files in this pass.
- Do not delete the GKE cluster automatically unless the user separately approves infrastructure teardown.
- Do not change API/frontend deployment behavior except where summary output mentions the worker is disabled.

## Implementation Steps

### 1. Add a backend worker flag

Edit `app/backend/app/core/config.py`:

- Add `worker_enabled: bool = False` to `Settings`.
- This should map to `WORKER_ENABLED` through the existing pydantic-settings environment handling.
- Keep `redis_enabled: bool = True` unchanged.

Add a small worker entrypoint module, for example `app/backend/app/workers/run_worker.py`:

- Load settings.
- If `settings.worker_enabled` is false, log a clear message like `Celery worker disabled by WORKER_ENABLED=false` and exit `0`.
- If true, start Celery with the existing app, equivalent to:

```python
celery_app.worker_main(["worker", "--loglevel=info"])
```

Keep `app/backend/app/workers/celery_app.py` importable so existing smoke tests and future worker code continue to work.

### 2. Make local worker startup opt-in

Edit `infra/docker/docker-compose.yml`:

- Add `profiles: ["worker"]` to the `worker` service so default `docker compose up` does not start it.
- Change the worker command to run the guarded entrypoint, for example:

```yaml
command: python -m app.workers.run_worker
```

- Set `WORKER_ENABLED: "true"` inside the worker service, because selecting the `worker` profile is the explicit local opt-in.

Update local docs that mention the worker:

- `README.md`
- `docs/requirements/01-local-docker-runtime.md`, if it still describes the worker as always-on.

Document local opt-in as:

```bash
docker compose --profile worker --profile redis up
```

### 3. Make CI/CD worker deployment opt-in

Edit `.github/workflows/deploy.yml`.

Add an environment flag near the existing deployment env block:

```yaml
WORKER_DEPLOY_ENABLED: ${{ vars.WORKER_DEPLOY_ENABLED || 'false' }}
```

Change the `prepare` job's `Resolve inputs` shell script:

- Keep `target=all`, `api`, `frontend`, and `terraform` behavior unchanged.
- Compute whether the worker was requested:

```bash
if [[ "${target}" == "all" || "${target}" == "worker" ]]; then
  requested_worker=true
else
  requested_worker=false
fi
```

- Set `deploy_worker=true` only when both conditions are true:

```bash
[[ "${requested_worker}" == "true" && "${WORKER_DEPLOY_ENABLED}" == "true" ]]
```

- Otherwise output `deploy_worker=false`.
- Add a prepare output like `worker_deploy_enabled` or `worker_disabled_reason` so the summary can explain why the worker was skipped.

Expected behavior:

- Push to `main`: API/frontend still deploy, worker does not build or deploy.
- Manual `target=all`: API/frontend deploy, worker skips unless `WORKER_DEPLOY_ENABLED=true`.
- Manual `target=worker`: skips unless `WORKER_DEPLOY_ENABLED=true`.
- To re-enable later, set repository/environment variable `WORKER_DEPLOY_ENABLED=true`.

In `deploy-worker`, add `WORKER_ENABLED=true` to the worker deployment environment when it is actually deployed. Because `infra/k8s/celery-worker/deployment.yaml` is static, either:

- add `WORKER_ENABLED: "true"` directly to the manifest, since the manifest is only applied when worker deployment is enabled; or
- patch it in the workflow before `kubectl apply`.

Prefer the first option for simplicity.

### 4. Keep the Kubernetes manifest, but mark it opt-in

Edit `infra/k8s/celery-worker/deployment.yaml`:

- Add `WORKER_ENABLED` with value `"true"` to the worker container env.
- Add a short comment near the manifest top explaining that this manifest is applied only when `WORKER_DEPLOY_ENABLED=true`.

Do not delete the manifest. It is still useful if the worker becomes real later.

### 5. Provide an explicit current-cloud deactivation script

CI changes prevent future worker deploys, but they do not stop the worker pod already running in GKE.

Add a script such as `scripts/deactivate-gke-worker.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-dachjob-ai-platform}"
REGION="${REGION:-europe-west1}"
GKE_CLUSTER_NAME="${GKE_CLUSTER_NAME:-dachjob-dev-cluster}"
GKE_NAMESPACE="${GKE_NAMESPACE:-celery-worker}"

gcloud container clusters get-credentials "${GKE_CLUSTER_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}"

kubectl scale deployment/celery-worker \
  --namespace="${GKE_NAMESPACE}" \
  --replicas=0

kubectl get pods --namespace="${GKE_NAMESPACE}" -o wide
```

Use `scale replicas=0` as the first safe deactivation step. It is reversible:

```bash
kubectl scale deployment/celery-worker --namespace=celery-worker --replicas=1
```

Only delete the deployment/HPA/namespace in a later cleanup if the user confirms that the worker will not come back.

### 6. Terraform handling

Do not destroy GKE automatically in this implementation.

Reason: `infra/terraform/main.tf` currently creates the GKE cluster unconditionally. Adding `count = var.enable_worker_infrastructure ? 1 : 0` with a default of `false` would cause a future Terraform apply to plan deletion of the existing GKE cluster. That may be desired later for cost cleanup, but it is too destructive for this default-worker-off change.

For this pass:

- Keep Terraform GKE resources unchanged.
- Add a follow-up TODO in `infra/terraform/README.md` documenting that GKE exists only for the disabled worker and can be gated or destroyed in a separately approved infrastructure cleanup.
- If the user explicitly approves teardown later, implement a separate plan with `enable_worker_infrastructure` and carefully update outputs that currently assume `module.gke` exists.

### 7. Update documentation

Update:

- `README.md`
- `infra/terraform/README.md`
- `docs/deployment/gcp-architecture.md`

Docs should say:

- Redis/Memorystore remains active for API caching and rate limiting.
- Celery worker is currently disabled by default because no production code enqueues jobs.
- Worker can be re-enabled with `WORKER_ENABLED=true` plus `WORKER_DEPLOY_ENABLED=true`.
- The GKE worker pod can be scaled down with `scripts/deactivate-gke-worker.sh`.

## Validation Checklist

Run locally:

```bash
cd app/backend
pytest tests/ --ignore=tests/test_provider_smoke.py -v
```

Validate config:

```bash
cd app/backend
python - <<'PY'
from app.core.config import get_settings
settings = get_settings()
assert settings.redis_enabled is True
assert settings.worker_enabled is False
print("redis_enabled", settings.redis_enabled)
print("worker_enabled", settings.worker_enabled)
PY
```

Validate local compose defaults:

```bash
docker compose config --services
```

The default service list should not include `worker` unless the worker profile is selected.

Validate workflow logic by reading the rendered shell logic:

- `target=all`, `WORKER_DEPLOY_ENABLED=false` should produce `deploy_worker=false`.
- `target=worker`, `WORKER_DEPLOY_ENABLED=false` should produce `deploy_worker=false`.
- `target=worker`, `WORKER_DEPLOY_ENABLED=true` should produce `deploy_worker=true`.

Validate current GKE deactivation manually after merge/deploy:

```bash
scripts/deactivate-gke-worker.sh
kubectl get hpa,deploy,pods -n celery-worker
```

Expected result:

- `deployment/celery-worker` has `0` desired replicas.
- No running `celery-worker-*` pod remains.
- Redis/Memorystore remains up.
- Cloud Run API `/api/health` still reports Redis ok.

## Acceptance Criteria

- API Redis caching remains enabled and healthy.
- Worker code remains present but is guarded by `WORKER_ENABLED=false` by default.
- Local Docker Compose does not start the worker by default.
- GitHub Actions `target=all` no longer builds or deploys the worker by default.
- Existing GKE worker can be scaled to zero with a checked-in script.
- Re-enabling worker later is documented and requires explicit flags.
