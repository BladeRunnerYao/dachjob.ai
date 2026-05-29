# Agent B Plan: Runtime Security, IAM, Secrets, and Docker Hardening

## Mission

Reduce the highest security risks without changing application behavior or restructuring Terraform directories.

This agent owns:

- runtime container hardening
- initial GCP IAM tightening
- Terraform-managed secret inventory
- safe handling recommendations for secrets

## Context

The architecture review found:

- GCP IAM currently grants overly broad permissions, including `roles/editor`.
- Terraform state may contain sensitive secret values.
- Backend Docker image creates a non-root user but may not use it.
- Backend runtime may install development dependencies.
- Frontend runtime image may be larger and more privileged than necessary.

## Files to Inspect First

```text
app/backend/Dockerfile
app/frontend/Dockerfile
app/backend/pyproject.toml
app/frontend/package.json
app/frontend/next.config.ts
infra/terraform/modules/iam/main.tf
infra/terraform/modules/secret-manager/main.tf
infra/terraform/modules/aws/**
infra/terraform/modules/azure/**
infra/terraform/live/**
.gitignore
```

Search terms:

```bash
grep -R "roles/editor\|roles/owner\|roles/iam.securityAdmin\|roles/secretmanager.admin" infra/terraform
grep -R "random_password\|secret_version\|password\|api_key\|sensitive" infra/terraform
```

## Implementation Steps

### Step 1: Harden backend Dockerfile

Open:

```text
app/backend/Dockerfile
```

Check whether it:

- installs dev dependencies with `.[dev]`
- creates a non-root user
- switches to that non-root user
- copies only required files

Required changes:

1. Runtime install should use production dependencies:

   ```dockerfile
   RUN pip install --no-cache-dir .
   ```

   not:

   ```dockerfile
   RUN pip install -e ".[dev]"
   ```

2. If an `app` user exists, the final image must include:

   ```dockerfile
   USER app
   ```

3. Preserve the existing command, exposed port, and startup behavior.

4. Do not remove dependencies needed at runtime.

If editable installs are currently required because package metadata is not copied correctly, fix the copy order instead of keeping dev install.

### Step 2: Harden frontend Dockerfile

Open:

```text
app/frontend/Dockerfile
```

Target model:

```dockerfile
FROM node:26-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM node:26-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:26-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN addgroup -S nodejs && adduser -S nextjs -G nodejs
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/node_modules ./node_modules
USER nextjs
EXPOSE 3000
CMD ["npm", "start"]
```

Adjust for the repository's actual Next.js setup.

If `output: "standalone"` is not configured, do not assume standalone output exists. Either:

- keep `npm start` with production dependencies, or
- add standalone only if validated by build and aligned with Next.js 16 docs.

Required:

- runtime user must be non-root
- runtime must set `NODE_ENV=production`
- build must still work

### Step 3: Create a secrets inventory

Create:

```text
docs/secrets.md
```

If the file already exists, update it rather than replacing unrelated content.

Required sections:

```markdown
# Secrets Inventory

## Purpose

This document records where runtime secrets are defined, how they are injected, and whether their values are stored in Terraform state.

## Inventory

| Secret | Cloud | Terraform location | Runtime consumer | Value in Terraform state? | Current injection method | Recommended owner |
|---|---|---|---|---|---|---|

## Handling Rules

- Terraform may create secret containers and IAM bindings.
- Prefer injecting secret values through cloud secret managers or protected CI operations.
- Do not commit `.tfvars`, `.env`, generated state, or secret values.
- Treat Terraform state as sensitive.
```

Populate the table with secrets discovered in `infra/terraform`.

Examples of things to check:

- DB password
- JWT secret
- LLM provider API keys
- storage credentials
- Redis auth if present
- OAuth / OIDC values if present

Do not include actual secret values.

### Step 4: Reduce obvious secret state exposure where safe

Do not attempt a risky migration of every existing secret.

Safe changes are allowed when they do not break deployment:

- mark variables as `sensitive = true`
- avoid outputting secret values
- remove unused secret outputs
- ensure `.gitignore` excludes local secret files
- create secret metadata without secret value for newly added secrets

Do not replace working secret provisioning with an untested external process in this task.

### Step 5: Remove GCP `roles/editor`

Open:

```text
infra/terraform/modules/iam/main.tf
```

Find grants of:

```text
roles/editor
```

Replace with narrower roles. Exact roles depend on current resources, but likely categories are:

For Terraform apply service account:

- `roles/compute.networkAdmin`
- `roles/run.admin`
- `roles/cloudsql.admin`
- `roles/redis.admin`
- `roles/artifactregistry.admin`
- `roles/secretmanager.admin` if Terraform manages secrets
- `roles/iam.serviceAccountAdmin` if it creates service accounts
- `roles/iam.serviceAccountUser` on specific runtime service accounts

For deploy service account:

- `roles/run.developer`
- `roles/artifactregistry.writer`
- `roles/iam.serviceAccountUser` on runtime service account

For runtime service account:

- `roles/secretmanager.secretAccessor`
- storage bucket-scoped access
- Cloud SQL connection role if used

Do not blindly grant all listed roles. Read the module and assign only what current resources require.

### Step 6: Reduce other broad GCP roles if straightforward

Review:

```text
roles/iam.securityAdmin
roles/secretmanager.admin
project-level admin roles
```

If a role is only needed for a narrow resource, scope it down.

If scoping down is too risky for this PR, leave a TODO in `docs/secrets.md` or a short comment in the plan summary, but at minimum remove `roles/editor`.

## Validation Commands

Backend image:

```bash
docker build -f app/backend/Dockerfile app/backend
```

Frontend image:

```bash
docker build -f app/frontend/Dockerfile app/frontend
```

Backend checks:

```bash
cd app/backend
pip install -e ".[dev]"
ruff check .
ruff format --check .
pytest tests/ --ignore=tests/test_provider_smoke.py -v
```

Frontend checks:

```bash
cd app/frontend
npm ci
npm run lint
npm run build
```

Terraform checks:

```bash
terraform fmt -check -recursive infra/terraform
terraform -chdir=infra/terraform init -backend=false
terraform -chdir=infra/terraform validate
terraform -chdir=infra/terraform/live/aws/dev init -backend=false
terraform -chdir=infra/terraform/live/aws/dev validate
terraform -chdir=infra/terraform/live/azure/dev init -backend=false
terraform -chdir=infra/terraform/live/azure/dev validate
```

Security search:

```bash
grep -R "roles/editor" infra/terraform || true
grep -R "USER root" app/backend app/frontend || true
```

Expected:

- no `roles/editor`
- runtime Dockerfiles use non-root users

## Acceptance Criteria

- Backend container does not install dev dependencies for runtime.
- Backend final image runs as non-root.
- Frontend runtime runs as non-root.
- `docs/secrets.md` exists and inventories Terraform-managed secrets.
- No actual secret values are written to documentation.
- GCP `roles/editor` is removed.
- Terraform validates.
- Docker builds succeed.

## Do Not Do

- Do not restructure Terraform directories.
- Do not change deployment workflow behavior except if needed for IAM variable names.
- Do not rotate secrets in this PR unless explicitly requested.
- Do not print secret values in logs.

