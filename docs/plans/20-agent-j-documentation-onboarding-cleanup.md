# Agent J Plan: Documentation and Onboarding Cleanup

## Mission

Make repository documentation accurately reflect the actual architecture, Terraform layout, deployment workflows, and environment model.

This is a documentation-only task unless a tiny broken path reference must be corrected.

## Context

The architecture review found documentation drift:

- Some docs mention old Terraform layout.
- Some docs imply staging/prod are implemented when only dev roots exist.
- Some docs reference AWS details or files inconsistently.
- `.github/copilot-instructions.md`, `AGENTS.md`, README, and Terraform docs overlap.

The goal is to reduce onboarding confusion for engineers and AI agents.

## Files to Inspect First

```text
README.md
AGENTS.md
.github/copilot-instructions.md
infra/terraform/README.md
docs/**/*.md
app/frontend/AGENTS.md
app/frontend/CLAUDE.md
```

Search:

```bash
grep -R "docs/aws-setup.md\|infra/terraform/main.tf\|environments/dev\|staging\|prod\|deploy-gcp.yml\|deploy-azure.yml\|deploy-aws.yml" README.md AGENTS.md .github/copilot-instructions.md infra/terraform/README.md docs app/frontend || true
```

## Desired End State

Docs should clearly state:

- frontend structure
- backend structure
- current deployment workflows
- current Terraform roots
- which environments actually exist
- multi-cloud support status
- where build/test/lint commands live

Docs should not claim future target architecture is already implemented.

## Implementation Steps

### Step 1: Inventory current factual architecture

Verify current directories:

```bash
find app -maxdepth 3 -type d | sort
find infra/terraform -maxdepth 4 -type d | sort
find .github/workflows -maxdepth 1 -type f | sort
```

Use actual output to update docs.

Do not add exhaustive directory listings to docs. Use only important paths.

### Step 2: Update README if needed

Open:

```text
README.md
```

Ensure it accurately describes:

- Next.js frontend
- FastAPI backend
- PostgreSQL/Redis/object storage/LLM gateway
- multi-cloud deployment support
- where to run backend commands
- where to run frontend commands
- where Terraform lives

Keep README concise. Do not add long operational runbooks if docs already exist elsewhere.

### Step 3: Update `AGENTS.md`

Open:

```text
AGENTS.md
```

Fix:

- missing or stale docs references
- Terraform root paths
- workflow behavior
- environment status

If it references:

```text
docs/aws-setup.md
```

verify the file exists. If not, either:

- remove the reference, or
- replace it with an existing doc path

Do not invent cloud credentials or secrets.

### Step 4: Update `.github/copilot-instructions.md`

Open:

```text
.github/copilot-instructions.md
```

Ensure it contains:

- current build/test/lint commands
- single-test examples
- high-level architecture
- key codebase conventions
- current Terraform layout
- current deployment workflow names
- environment reality

If Agent C has already moved GCP root to `live/gcp/dev`, update the GCP path.

If Agent C has not moved it, document current reality:

```text
GCP root: infra/terraform
Azure root: infra/terraform/live/azure/dev
AWS root: infra/terraform/live/aws/dev
```

Do not overstate staging/prod readiness.

### Step 5: Update Terraform README

Open:

```text
infra/terraform/README.md
```

It should clearly show:

```text
Current roots:
- GCP:   ...
- Azure: ...
- AWS:   ...
```

Also document:

- remote state locations if already known and non-secret
- how to run `terraform validate`
- how to run `terraform plan`
- that secrets/state are sensitive

Do not include actual secret values.

### Step 6: Add a concise multi-cloud status table

In the most appropriate doc, add:

```markdown
| Cloud | Runtime | Database | Cache | Storage | Terraform root | Deploy workflow | Environment implemented |
|---|---|---|---|---|---|---|---|
| GCP | Cloud Run / GKE worker | Cloud SQL | Memorystore | GCS | ... | deploy-gcp.yml | dev |
| Azure | Container Apps | PostgreSQL Flexible Server | Azure Cache for Redis | Blob Storage | ... | deploy-azure.yml | dev |
| AWS | ECS Fargate | RDS PostgreSQL | ElastiCache | S3 | ... | deploy-aws.yml | dev |
```

Use actual repo state. If a cloud differs, document the real state.

### Step 7: Clarify environment model

Add a short section:

```markdown
## Environment Model

The repository currently has Terraform roots for `dev`. Workflow inputs may mention `staging` and `prod`, but those environments require corresponding Terraform roots, backend state, GitHub Environments, and secrets before they are production-ready.
```

If staging/prod have been implemented by another agent, update accordingly.

### Step 8: Remove stale references

Run:

```bash
grep -R "docs/aws-setup.md" README.md AGENTS.md .github/copilot-instructions.md infra/terraform/README.md docs || true
grep -R "infra/terraform/main.tf" README.md AGENTS.md .github/copilot-instructions.md infra/terraform/README.md docs || true
grep -R "infra/terraform/environments/dev" README.md AGENTS.md .github/copilot-instructions.md infra/terraform/README.md docs || true
```

For each match:

- if still accurate, keep it
- if stale, update it
- if referencing missing file, remove or replace

### Step 9: Avoid duplicating long docs

Where multiple docs overlap:

- README: short project overview and common commands
- AGENTS/copilot instructions: AI agent operational rules and key conventions
- Terraform README: Terraform-specific workflow
- docs: detailed plans/runbooks

Do not copy the same long section into all files.

## Validation Commands

Run:

```bash
grep -R "docs/aws-setup.md" README.md AGENTS.md .github/copilot-instructions.md infra/terraform/README.md docs || true
grep -R "TODO.*update docs" README.md AGENTS.md .github/copilot-instructions.md infra/terraform/README.md docs || true
```

If markdown lint exists, run it. Do not add a new markdown lint dependency.

Check git diff:

```bash
git diff -- README.md AGENTS.md .github/copilot-instructions.md infra/terraform/README.md docs
```

Ensure no secret values were added.

## Acceptance Criteria

- Docs accurately describe current frontend/backend/deployment/Terraform architecture.
- Terraform root paths are correct.
- Environment status is clear and not overstated.
- No references to missing docs remain.
- No secret values are added.
- Changes are documentation-only unless a tiny path reference required correction.

## Do Not Do

- Do not change application code.
- Do not change Terraform resources.
- Do not change workflows.
- Do not add generic best-practice sections.
- Do not document future target state as current state.
