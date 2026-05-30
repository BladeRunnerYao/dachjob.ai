# Agent A Plan: CI/CD Safety Boundary

## Mission

Make deployment workflows safe and deterministic before any larger infrastructure or application refactor happens.

This agent owns only GitHub Actions deployment safety. Do not refactor Terraform modules, backend code, frontend code, or Dockerfiles in this task.

## Context

The repository currently has three provider-specific deployment workflows:

- `.github/workflows/deploy-gcp.yml`
- `.github/workflows/deploy-azure.yml`
- `.github/workflows/deploy-aws.yml`

The architecture review identified these risks:

- Pull requests can trigger deployment workflows.
- Deployment jobs hardcode `environment: dev`.
- Terraform apply can run because `target=terraform` is selected, even when explicit apply is not requested.
- AWS password reset logic is embedded in deployment.
- Worker deploy failures can be ignored through `continue-on-error`.

## Desired End State

1. Pull requests run validation only.
2. Deployment workflows do not run on pull requests.
3. GitHub Environment is selected from the workflow input / prepare output, not hardcoded to `dev`.
4. Terraform apply runs only when explicitly requested.
5. AWS password reset is moved to a separate protected manual workflow.
6. Worker deployment failure blocks the release when worker deployment is enabled.

## Files to Inspect First

Read these files before editing:

```text
.github/workflows/deploy-gcp.yml
.github/workflows/deploy-azure.yml
.github/workflows/deploy-aws.yml
app/backend/pyproject.toml
app/frontend/package.json
infra/terraform/README.md
```

Look for:

- `on: pull_request`
- `environment: dev`
- `terraform_apply`
- `target == 'terraform'`
- `continue-on-error`
- `reset_password_for`
- backend test commands
- frontend lint/build commands
- Terraform validation paths

## Implementation Steps

### Step 1: Create a dedicated CI workflow

Create:

```text
.github/workflows/ci.yml
```

Use this structure:

```yaml
name: CI

on:
  pull_request:
  push:
    branches:
      - main

permissions:
  contents: read

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  backend:
    name: Backend lint and tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - name: Install backend dependencies
        run: |
          cd app/backend
          pip install -e ".[dev]"
      - name: Ruff check
        run: |
          cd app/backend
          ruff check .
      - name: Ruff format check
        run: |
          cd app/backend
          ruff format --check .
      - name: Tests
        run: |
          cd app/backend
          pytest tests/ --ignore=tests/test_provider_smoke.py -v

  frontend:
    name: Frontend lint and build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "26"
          cache: npm
          cache-dependency-path: app/frontend/package-lock.json
      - name: Install frontend dependencies
        run: |
          cd app/frontend
          npm ci
      - name: Lint frontend
        run: |
          cd app/frontend
          npm run lint
      - name: Build frontend
        run: |
          cd app/frontend
          npm run build

  terraform:
    name: Terraform validate
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      - name: Terraform fmt
        run: terraform fmt -check -recursive infra/terraform
      - name: Validate GCP Terraform
        run: |
          terraform -chdir=infra/terraform/live/gcp/dev init -backend=false
          terraform -chdir=infra/terraform/live/gcp/dev validate
      - name: Validate AWS Terraform
        run: |
          terraform -chdir=infra/terraform/live/aws/dev init -backend=false
          terraform -chdir=infra/terraform/live/aws/dev validate
      - name: Validate Azure Terraform
        run: |
          terraform -chdir=infra/terraform/live/azure/dev init -backend=false
          terraform -chdir=infra/terraform/live/azure/dev validate
```

Adjust only if current repository paths differ. If Agent C has already moved GCP Terraform to `infra/terraform/live/gcp/dev`, validate that path instead.

### Step 2: Remove PR triggers from deployment workflows

In each deploy workflow, remove `pull_request` from `on`.

Allowed deployment triggers:

```yaml
on:
  workflow_dispatch:
    inputs:
      ...
  push:
    branches:
      - main
```

If the repo owner prefers manual deploy only, use only:

```yaml
on:
  workflow_dispatch:
```

Do not leave `pull_request` in any deploy workflow.

### Step 3: Replace hardcoded GitHub Environment

Search:

```bash
grep -R "environment: dev" .github/workflows/deploy-*.yml
```

Replace deployment job environments with the normalized output from the prepare job:

```yaml
environment: ${{ needs.prepare.outputs.environment }}
```

If the workflow currently uses a different prepare output name, use that exact output. The goal is that a manual dispatch with `environment=staging` uses GitHub Environment `staging`.

Do not replace non-deployment local environment variables accidentally. Only replace GitHub Actions job-level `environment:`.

### Step 4: Fix Terraform apply conditions

Search:

```bash
grep -R "terraform_apply" .github/workflows/deploy-*.yml
grep -R "target.*terraform" .github/workflows/deploy-*.yml
```

Find any apply condition equivalent to:

```yaml
if: inputs.terraform_apply == 'true' || target == 'terraform'
```

Replace with a condition that requires explicit apply:

```yaml
if: needs.prepare.outputs.terraform_apply == 'true'
```

or:

```yaml
if: github.event.inputs.terraform_apply == 'true'
```

Use the existing normalized output if present.

Required behavior:

| Target | Terraform apply input | Expected behavior |
|---|---|---|
| `terraform` | `false` | plan only |
| `terraform` | `true` | plan and apply |
| `all` | `false` | no apply |
| `all` | `true` | apply before deploy |

Terraform plan may still run for `target=terraform`. Terraform apply must not.

### Step 5: Move AWS password reset to a separate admin workflow

Inspect:

```text
.github/workflows/deploy-aws.yml
```

Remove:

- `reset_password_for` input
- steps that call forgot-password / reset-password APIs
- summary output for password reset

Create:

```text
.github/workflows/admin-password-reset.yml
```

Recommended structure:

```yaml
name: Admin Password Reset

on:
  workflow_dispatch:
    inputs:
      email:
        description: Email address to reset
        required: true
        type: string
      environment:
        description: Target environment
        required: true
        type: choice
        default: dev
        options:
          - dev
          - staging
          - prod

permissions:
  contents: read
  id-token: write

jobs:
  reset-password:
    name: Reset user password
    runs-on: ubuntu-latest
    environment: admin
    steps:
      - uses: actions/checkout@v4
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_DEPLOY_ROLE_ARN }}
          aws-region: eu-west-1
      - name: Reset password
        env:
          RESET_EMAIL: ${{ github.event.inputs.email }}
          TARGET_ENVIRONMENT: ${{ github.event.inputs.environment }}
        run: |
          echo "Implement reset flow using existing deploy-aws logic, without printing tokens."
```

When porting existing logic, do not print reset tokens or passwords into logs. Mask sensitive values with `::add-mask::`.

### Step 6: Make worker deploy failures blocking when enabled

Search:

```bash
grep -R "continue-on-error" .github/workflows/deploy-*.yml
```

For worker deploy jobs:

- remove unconditional `continue-on-error: true`
- skip worker deploy when worker mode is disabled
- fail the workflow if worker mode is enabled and worker deploy fails

Acceptable pattern:

```yaml
if: needs.prepare.outputs.worker_mode == 'enabled'
```

Do not silently mark failed worker deploys as successful.

## Validation Commands

Run:

```bash
git diff -- .github/workflows
```

If available:

```bash
actionlint .github/workflows/*.yml
```

Otherwise use:

```bash
python - <<'PY'
import yaml, glob
for path in glob.glob(".github/workflows/*.yml"):
    with open(path) as f:
        yaml.safe_load(f)
    print(f"ok {path}")
PY
```

Also run these searches:

```bash
grep -R "pull_request" .github/workflows/deploy-*.yml || true
grep -R "environment: dev" .github/workflows/deploy-*.yml || true
grep -R "reset_password_for" .github/workflows/deploy-aws.yml || true
grep -R "continue-on-error: true" .github/workflows/deploy-*.yml || true
```

Expected:

- no `pull_request` in deploy workflows
- no job-level `environment: dev` in deploy workflows
- no `reset_password_for` in AWS deploy workflow
- no unconditional worker `continue-on-error: true`

## Acceptance Criteria

- New `.github/workflows/ci.yml` exists.
- PRs run CI only.
- Deployment workflows do not run on PR.
- Deployment workflows select GitHub Environment dynamically.
- Terraform apply requires explicit confirmation.
- AWS password reset is isolated in a protected admin workflow.
- Enabled worker deployment failures block releases.

## Do Not Do

- Do not change Terraform resource definitions.
- Do not change application code.
- Do not change Dockerfiles.
- Do not introduce a large reusable workflow refactor; that is Agent D's task.
