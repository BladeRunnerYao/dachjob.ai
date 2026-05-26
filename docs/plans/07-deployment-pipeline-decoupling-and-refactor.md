# Deployment Pipeline Decoupling And Refactor Brief

## Purpose

This branch is intended to become the implementation branch for decoupling the
GCP and Azure deployment pipelines and cleaning up the highest-risk refactor
areas in the repository.

The main objective is to stop changes for one cloud provider from accidentally
breaking the other. The current deployment workflow mixes GCP and Azure logic in
one large GitHub Actions file with many conditional branches. The target state is
two independent deployment paths:

- Deploy to GCP
- Deploy to Azure

Each pipeline must authenticate, build, deploy, migrate, and smoke-test only its
own cloud.

## Current Findings

### Deployment Coupling

The current combined deployment workflow contains:

- One `cloud` input with `gcp`, `azure`, and `all`.
- GCP and Azure environment variables in the same global `env` block.
- GCP and Azure authentication steps in the same jobs.
- GCP and Azure image metadata in the same build jobs.
- GCP Cloud Run, GKE, Azure Container Apps, and migration logic in the same
  deploy jobs.
- A GCP worker scale-down job that is not sufficiently isolated from Azure
  deploys.

This makes it easy for a fix in one provider path to regress the other.

### Infrastructure State And Secrets

The repository currently contains Azure Terraform under
`infra/terraform/live/azure/dev`, while GCP Terraform still lives at the older
root `infra/terraform` layout.

There is also a real Azure `terraform.tfvars` file in the repo containing a
Postgres administrator password. This must be treated as exposed and rotated.

### Code Refactor Hotspots

The following areas are large enough to make changes risky:

- `app/backend/app/modules/matching/service.py`
- `app/backend/app/modules/jobs/importer.py`
- `app/frontend/src/lib/api/client.ts`
- `app/frontend/src/components/jobs/job-description-view.tsx`

The backend is generally modular at the route/repository level, but several
service files combine parsing, provider integration, business scoring, fallback
logic, and persistence in one place.

## Target Design

### GitHub Actions

Create two separate workflows:

- `.github/workflows/deploy-gcp.yml`
- `.github/workflows/deploy-azure.yml`

Remove or disable the old combined `.github/workflows/deploy.yml` after both new
workflows are in place.

Do not keep a `cloud` input in either new workflow. The workflow file itself is
the provider selection.

Shared manual inputs for both workflows:

- `environment`: `dev`, `staging`, or `prod`
- `branch`: optional branch override
- `target`: `all`, `api`, `frontend`, `worker`, or `terraform`
- `terraform_apply`: boolean
- `run_migrations`: boolean
- `worker_mode`: `disabled` or `enabled`
- `smoke_test_mode`: `minimal` or `full`

Default to:

- `environment=dev`
- `target=all`
- `terraform_apply=false`
- `run_migrations=true`
- `worker_mode=disabled`
- `smoke_test_mode=minimal`

### GCP Workflow Responsibilities

The GCP workflow must contain only GCP-specific logic:

- Checkout selected branch.
- Run backend lint/tests.
- Authenticate to GCP with Workload Identity Federation.
- Optionally run Terraform from the GCP Terraform directory.
- Build and push API, frontend, and worker images to Artifact Registry.
- Deploy API and frontend to Cloud Run.
- Run migrations through a Cloud Run job.
- Deploy the worker to GKE only when `worker_mode=enabled`.
- Scale down the GKE worker only in the GCP workflow and only when explicitly
  requested by the worker settings.
- Run post-deploy smoke tests against the deployed GCP URLs.

The GCP workflow must not reference:

- Azure OIDC login
- Azure Container Registry
- Azure Container Apps
- Azure resource groups
- Azure Terraform directories

### Azure Workflow Responsibilities

The Azure workflow must contain only Azure-specific logic:

- Checkout selected branch.
- Run backend lint/tests.
- Authenticate to Azure with GitHub OIDC.
- Optionally run Terraform under `infra/terraform/live/azure/dev`.
- Build and push API, frontend, and worker images to Azure Container Registry.
- Deploy API, frontend, and worker to Azure Container Apps.
- Run migrations through an Azure Container Apps job.
- Run post-deploy smoke tests against the deployed Azure URLs.

The Azure workflow must not reference:

- GCP Workload Identity Federation
- `gcloud`
- Artifact Registry
- Cloud Run
- GKE
- GCP Terraform backend files

### Deployment Scripts

Keep script boundaries explicit and provider-specific.

Shared script:

- `infra/deploy/scripts/build-image.sh`

GCP scripts:

- `infra/deploy/scripts/deploy-gcp.sh`
- `infra/deploy/scripts/run-migrations-gcp.sh`

Azure scripts:

- `infra/deploy/scripts/deploy-azure.sh`
- `infra/deploy/scripts/run-migrations-azure.sh`

Shared verification script:

- `infra/deploy/scripts/smoke-test-api.sh`

Fix the Azure deploy script contract. It should accept exactly:

```bash
deploy-azure.sh <target> <api_image> <frontend_image> <worker_image>
```

Do not pass migration flags to this script. Migrations belong in
`run-migrations-azure.sh`.

## Implementation Phases

### Phase 1: Safety Cleanup

1. Add ignore rules for local/generated deployment artifacts:
   - `.codegraph/`
   - `*.tfvars`
   - `*.tfstate`
   - `*.tfstate.*`
   - `.terraform/`
   - `*.tfplan`

2. Remove committed real tfvars:
   - Delete the real Azure `terraform.tfvars`.
   - Keep only `terraform.tfvars.example`.

3. Rotate exposed secrets:
   - Rotate the Azure Postgres administrator password that was committed.
   - Confirm no GitHub Actions secrets or cloud credentials are committed.

4. Update docs to say real tfvars files must be created locally or supplied by
   CI, never committed.

Acceptance:

- `git status` contains no committed secret values.
- `.gitignore` prevents future tfvars/state/plan files from being added.
- The Azure password is rotated outside this repo.

### Phase 2: Split Workflows

1. Create `.github/workflows/deploy-gcp.yml`.
2. Move GCP-only jobs from the old workflow into the GCP workflow.
3. Create `.github/workflows/deploy-azure.yml`.
4. Move Azure-only jobs from the old workflow into the Azure workflow.
5. Remove all `cloud == ...` conditionals from the new workflows.
6. Replace provider-specific global env blocks with GitHub Environment variables
   and workflow-specific env blocks.
7. Ensure each workflow uses its own concurrency group:
   - `deploy-gcp-${environment}`
   - `deploy-azure-${environment}`

Acceptance:

- GCP workflow contains no Azure-specific commands or variables.
- Azure workflow contains no GCP-specific commands or variables.
- `target=terraform` does not build or deploy app images.
- `target=api` does not redeploy frontend or worker.
- `target=frontend` does not redeploy API or worker.
- `target=worker` does not redeploy API or frontend.

### Phase 3: Script Extraction

1. Move inline GCP deploy commands into `deploy-gcp.sh`.
2. Move inline Azure deploy commands into `deploy-azure.sh`.
3. Move GCP migration commands into `run-migrations-gcp.sh`.
4. Move Azure migration commands into `run-migrations-azure.sh`.
5. Keep `build-image.sh` cloud-neutral.
6. Add strict shell options to every script:

```bash
set -euo pipefail
```

7. Validate required env vars at the top of each script with clear error
   messages.

Acceptance:

- Workflow YAML becomes orchestration only.
- Cloud CLI details live in provider-specific scripts.
- Script parameter counts are documented and tested by shellcheck.

### Phase 4: Application Cloud-Neutral Cleanup

1. Storage:
   - Replace implicit GCS detection based on `S3_ENDPOINT_URL` with explicit
     `STORAGE_PROVIDER`.
   - Support `s3`, `gcs`, and `azure_blob`.
   - Keep local MinIO working with `STORAGE_PROVIDER=s3`.
   - Add fake-client unit tests for each storage backend.

2. LLM gateway:
   - Keep business modules calling only `LLMGateway.run_text()` and
     `LLMGateway.run_json()`.
   - Use a provider registry internally.
   - Keep `vertex_ai`, `gemini`, `deepseek`, `openrouter`, and `azure_openai`
     behind the same gateway interface.
   - Add tests for provider ordering and fallback.

3. Matching service:
   - Split skill taxonomy and regex extraction into a dedicated module.
   - Split JD parsing from match scoring.
   - Keep public functions compatible:
     - `parse_job_posting`
     - `compute_match`

4. Job importer:
   - Split fetch, HTML extraction, ATS-specific extraction, normalization, and
     persistence.
   - Keep route behavior compatible.
   - Add focused tests for supported ATS/source parsing.

5. Frontend API client:
   - Split the monolithic client into domain clients.
   - Keep the exported `api` facade for compatibility during the first pass.
   - Disable mock fallback in production.

Acceptance:

- Existing route contracts continue to work.
- Business modules do not import cloud SDKs directly.
- Local Docker Compose still works.
- Unit tests pass without live cloud credentials.

### Phase 5: Post-Deploy Cloud Request Smoke Tests

Add `infra/deploy/scripts/smoke-test-api.sh`.

Required inputs:

```bash
API_BASE_URL
FRONTEND_URL
SMOKE_TEST_EMAIL
SMOKE_TEST_PASSWORD
SMOKE_TEST_MODE
```

Recommended generated email format:

```text
smoke+<cloud>-<github_run_id>-<github_run_attempt>@example.com
```

The script must fail fast with useful logs if a required endpoint is unhealthy.

#### Minimal Smoke Test

The minimal smoke test is required after every deployment.

It must send real HTTP requests to the deployed cloud service:

1. `GET /api/health`
   - Expect HTTP 200.
   - Expect JSON `status=ok`.

2. `GET /api/version`
   - Expect HTTP 200.
   - Expect service/version fields.
   - Record `worker_enabled` and `worker_fallback_to_sync` in the workflow
     summary.

3. Register or login:
   - Try `POST /api/auth/register` with the generated smoke email.
   - If the user already exists, use `POST /api/auth/login`.
   - Extract Bearer token.

4. `GET /api/auth/me`
   - Use the Bearer token.
   - Expect HTTP 200 and the smoke email.

5. `POST /api/profile/cv`
   - Upload a small Markdown CV.
   - Expect HTTP 200 and a profile id.

6. `POST /api/jobs`
   - Create a small synthetic job posting.
   - Expect HTTP 201 and a job id.

7. `GET /api/jobs?limit=5&offset=0`
   - Expect HTTP 200 and a valid paginated response.

8. `GET /api/jobs/{job_id}`
   - Expect HTTP 200 and the same job id.

9. `GET /api/applications`
   - Expect HTTP 200 and an array.

10. `GET $FRONTEND_URL`
    - Expect HTTP 2xx or 3xx.

#### Full Smoke Test

The full smoke test is optional at first because it may use LLM calls, storage,
PDF generation, and workers.

It should be enabled manually or in a scheduled workflow after the minimal test
is stable.

Full mode should additionally test:

1. `POST /api/jobs/{job_id}/parse`
   - If the API returns a background task, poll `GET /api/tasks/{task_id}`.
   - Expect task status `succeeded`.

2. `POST /api/jobs/{job_id}/match`
   - Requires a profile to exist.
   - If background task mode is enabled, poll until terminal status.
   - Expect a match report or successful task result.

3. `POST /api/jobs/{job_id}/resume`
   - If background task mode is enabled, poll until terminal status.
   - Expect a resume artifact id.

4. `GET /api/resumes/{artifact_id}/html`
   - Expect HTTP 200 and HTML content.

5. `GET /api/resumes/{artifact_id}/pdf`
   - Expect HTTP 200 and `application/pdf`.

6. `GET /api/llm-runs?limit=5`
   - Expect HTTP 200 and valid pagination.

Acceptance:

- Minimal smoke test is a hard deploy gate for both clouds.
- Full smoke test can be configured as optional at first.
- The smoke test never needs credentials from the other cloud provider.
- Workflow summaries include API URL, frontend URL, smoke test mode, and smoke
  test result.

## Testing Checklist

Run these locally before opening a PR:

```bash
cd app/backend
pytest tests/ -v
```

```bash
cd app/frontend
npm run lint
npm run build
```

```bash
terraform fmt -check -recursive infra/terraform
terraform -chdir=infra/terraform/live/azure/dev init -backend=false
terraform -chdir=infra/terraform/live/azure/dev validate
```

```bash
actionlint .github/workflows/deploy-gcp.yml .github/workflows/deploy-azure.yml
shellcheck infra/deploy/scripts/*.sh
```

If `actionlint` or `shellcheck` is not available, install them in the CI image or
document the local install command.

## Cloud Acceptance Criteria

### GCP

- GCP deployment succeeds without any Azure secrets configured.
- GCP Terraform path does not read Azure Terraform files.
- API and frontend deploy to Cloud Run.
- Worker deploy or scale-down logic only touches GKE from the GCP workflow.
- Minimal post-deploy smoke test passes against the Cloud Run API and frontend
  URLs.

### Azure

- Azure deployment succeeds without any GCP secrets configured.
- Azure Terraform path does not read GCP backend files.
- API, frontend, and worker deploy to Azure Container Apps.
- Migration runs as an explicit Azure Container Apps job.
- Minimal post-deploy smoke test passes against the Azure API and frontend URLs.

### Cross-Cloud Isolation

- A GCP-only change cannot trigger Azure auth, Azure registry login, or Azure
  deploy commands.
- An Azure-only change cannot trigger GCP auth, GCP registry login, Cloud Run, or
  GKE commands.
- No workflow has a provider value named `all`.
- No workflow deploy job branches on `cloud == ...`.

## Rollout Order

1. Safety cleanup and secret rotation.
2. Add post-deploy smoke test script.
3. Add GCP-only workflow and validate it against dev.
4. Add Azure-only workflow and validate it against dev.
5. Disable or remove old combined deploy workflow.
6. Refactor storage and LLM provider boundaries.
7. Refactor matching and job importer internals.
8. Refactor frontend API client.
9. Optionally normalize GCP Terraform into `infra/terraform/live/gcp/dev` after
   both deploy workflows are stable.

## Assumptions

- The implementation branch is `codex/deployment-pipeline-decoupling`.
- The branch is based on `origin/main`.
- Deepseek will implement on this same branch later.
- The first version should prioritize safe decoupling over a large Terraform
  directory migration.
- Minimal smoke tests are required after every deploy.
- Full smoke tests are optional at first to avoid deployment instability from
  LLM provider quota, latency, PDF generation, and worker timing.
