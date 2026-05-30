# Agent D Plan: CI/CD Maintainability, Smoke Tests, and Drift Detection

## Mission

Reduce repeated deployment workflow logic, standardize smoke test behavior, and add Terraform drift detection.

This agent works after or alongside Agent A. If Agent A has not completed, avoid changing deployment safety semantics and focus only on reusable pieces that do not alter behavior.

## Context

Deployment workflows are long and repetitive:

- GCP workflow is about 800+ lines.
- Azure workflow is about 800+ lines.
- AWS workflow is about 900+ lines.

The repeated parts include:

- input normalization
- image tag calculation
- Docker Buildx setup/build/push
- smoke test execution
- deployment summaries

Provider-specific auth and deploy steps should remain explicit.

## Files to Inspect First

```text
.github/workflows/deploy-gcp.yml
.github/workflows/deploy-azure.yml
.github/workflows/deploy-aws.yml
infra/deploy/scripts/smoke-test-api.sh
infra/deploy/scripts/build-image.sh
```

## Desired End State

New composite actions:

```text
.github/actions/resolve-deploy-inputs/action.yml
.github/actions/docker-build-push/action.yml
.github/actions/smoke-test/action.yml
```

New workflow:

```text
.github/workflows/terraform-drift.yml
```

Deployment smoke test policy:

| Trigger | Default smoke mode |
|---|---|
| push to main | minimal |
| manual dispatch | minimal unless user selects full |
| scheduled smoke/drift | full or plan-only depending workflow |

## Implementation Steps

### Step 1: Extract input normalization action

Create:

```text
.github/actions/resolve-deploy-inputs/action.yml
```

Inputs:

```yaml
inputs:
  environment:
    required: false
    default: dev
  target:
    required: false
    default: all
  worker-mode:
    required: false
    default: disabled
  smoke-test-mode:
    required: false
    default: minimal
  terraform-apply:
    required: false
    default: "false"
  image-tag:
    required: false
    default: ""
```

Outputs:

```yaml
outputs:
  environment
  target
  worker_mode
  smoke_test_mode
  terraform_apply
  image_tag
```

Implementation:

- Use shell.
- Normalize empty inputs.
- Use commit SHA + run number if `image-tag` is empty.
- Do not include cloud-specific values.
- Validate allowed values for environment/target/worker-mode.

Suggested validation in action:

```bash
case "$ENVIRONMENT" in dev|staging|prod) ;; *) echo "Invalid environment"; exit 1 ;; esac
case "$TARGET" in all|terraform|api|frontend|worker) ;; *) echo "Invalid target"; exit 1 ;; esac
case "$WORKER_MODE" in enabled|disabled) ;; *) echo "Invalid worker mode"; exit 1 ;; esac
case "$SMOKE_TEST_MODE" in minimal|full|skip) ;; *) echo "Invalid smoke test mode"; exit 1 ;; esac
```

### Step 2: Extract Docker build/push action

Create:

```text
.github/actions/docker-build-push/action.yml
```

Inputs:

```yaml
inputs:
  context:
    required: true
  dockerfile:
    required: true
  image:
    required: true
  tags:
    required: true
  push:
    required: false
    default: "true"
  platforms:
    required: false
    default: linux/amd64
  build-args:
    required: false
    default: ""
```

Implementation:

- setup Buildx should remain in workflow or action; choose one consistently
- call `docker/build-push-action@v6`
- pass context/dockerfile/tags/push/platforms/build-args

Do not hardcode:

- GCP Artifact Registry
- Azure Container Registry
- AWS ECR

The workflows should pass full image names.

### Step 3: Extract smoke test action

Create:

```text
.github/actions/smoke-test/action.yml
```

Inputs:

```yaml
inputs:
  api-url:
    required: true
  frontend-url:
    required: false
    default: ""
  mode:
    required: false
    default: minimal
  auth-token:
    required: false
    default: ""
```

Implementation:

```yaml
runs:
  using: composite
  steps:
    - shell: bash
      env:
        API_URL: ${{ inputs.api-url }}
        FRONTEND_URL: ${{ inputs.frontend-url }}
        SMOKE_TEST_MODE: ${{ inputs.mode }}
        AUTH_TOKEN: ${{ inputs.auth-token }}
      run: |
        chmod +x infra/deploy/scripts/smoke-test-api.sh
        infra/deploy/scripts/smoke-test-api.sh
```

Ensure the script can run with missing frontend URL if current workflows support API-only smoke tests.

### Step 4: Update deploy workflows to use composite actions

For each deploy workflow:

```text
deploy-gcp.yml
deploy-azure.yml
deploy-aws.yml
```

Replace repeated input normalization with:

```yaml
- uses: ./.github/actions/resolve-deploy-inputs
  id: inputs
  with:
    environment: ${{ github.event.inputs.environment || 'dev' }}
    target: ${{ github.event.inputs.target || 'all' }}
    worker-mode: ${{ github.event.inputs.worker_mode || 'disabled' }}
    smoke-test-mode: ${{ github.event.inputs.smoke_test_mode || 'minimal' }}
    terraform-apply: ${{ github.event.inputs.terraform_apply || 'false' }}
    image-tag: ${{ github.event.inputs.image_tag || '' }}
```

Update prepare job outputs to consume action outputs.

Replace repeated smoke test step with:

```yaml
- uses: ./.github/actions/smoke-test
  with:
    api-url: ${{ needs.deploy-api.outputs.api_url }}
    frontend-url: ${{ needs.deploy-frontend.outputs.frontend_url }}
    mode: ${{ needs.prepare.outputs.smoke_test_mode }}
```

Replace build/push steps only where it is straightforward. If provider-specific registry auth makes it risky, leave build/push for a second PR.

### Step 5: Standardize smoke test defaults

In workflow inputs, set:

```yaml
smoke_test_mode:
  default: minimal
  type: choice
  options:
    - minimal
    - full
    - skip
```

Ensure push-to-main default is also minimal.

Avoid patterns where dispatch default says `minimal` but push fallback becomes `full`.

### Step 6: Add Terraform drift workflow

Create:

```text
.github/workflows/terraform-drift.yml
```

Suggested behavior:

```yaml
name: Terraform Drift Check

on:
  workflow_dispatch:
  schedule:
    - cron: "0 6 * * 1"

permissions:
  contents: read
  id-token: write

jobs:
  plan:
    name: Drift check (${{ matrix.cloud }}/${{ matrix.environment }})
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        include:
          - cloud: gcp
            environment: dev
            path: infra/terraform/live/gcp/dev
          - cloud: azure
            environment: dev
            path: infra/terraform/live/azure/dev
          - cloud: aws
            environment: dev
            path: infra/terraform/live/aws/dev
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      # add provider auth per cloud
      - name: Terraform init
        run: terraform -chdir=${{ matrix.path }} init
      - name: Terraform plan
        id: plan
        continue-on-error: true
        run: terraform -chdir=${{ matrix.path }} plan -detailed-exitcode -no-color
      - name: Interpret plan
        run: |
          case "${{ steps.plan.outcome }}" in
            success) echo "No drift or plan completed." ;;
            failure) echo "Terraform plan failed or drift detected."; exit 1 ;;
          esac
```

Important: `terraform plan -detailed-exitcode` uses exit code:

- `0`: no changes
- `2`: changes present
- `1`: error

GitHub Actions treats `2` as failure unless handled. Implement explicit handling:

```bash
set +e
terraform -chdir="$TF_PATH" plan -detailed-exitcode -no-color -out=tfplan
code=$?
set -e
if [ "$code" -eq 0 ]; then
  echo "No drift"
elif [ "$code" -eq 2 ]; then
  echo "Drift detected"
  exit 2
else
  echo "Plan failed"
  exit 1
fi
```

Do not apply.

### Step 7: Keep provider-specific deployment explicit

Do not abstract:

- `google-github-actions/auth`
- `azure/login`
- `aws-actions/configure-aws-credentials`
- `gcloud run deploy`
- `az containerapp update`
- `aws ecs update-service`

Only abstract common mechanical logic.

## Validation Commands

If available:

```bash
actionlint .github/workflows/*.yml .github/actions/*/action.yml
```

YAML parse fallback:

```bash
python - <<'PY'
import glob, yaml
for path in glob.glob(".github/workflows/*.yml") + glob.glob(".github/actions/*/action.yml"):
    with open(path) as f:
        yaml.safe_load(f)
    print("ok", path)
PY
```

Search:

```bash
grep -R "smoke_test_mode.*full" .github/workflows/deploy-*.yml || true
grep -R "terraform apply" .github/workflows/terraform-drift.yml && exit 1 || true
```

Expected:

- deploy default is minimal smoke
- drift workflow has no apply

## Acceptance Criteria

- Composite actions exist for input normalization, Docker build/push, and smoke test, or a documented subset if split into smaller PRs.
- Deploy workflows use at least the input and smoke test composite actions.
- Smoke test default is minimal.
- Full smoke test is opt-in or scheduled.
- Terraform drift workflow exists and never applies.
- Cloud-specific deploy steps remain readable and explicit.

## Do Not Do

- Do not change Terraform resources.
- Do not change backend/frontend source.
- Do not combine cloud auth/deploy into one generic abstraction.
- Do not make drift workflow apply changes.
