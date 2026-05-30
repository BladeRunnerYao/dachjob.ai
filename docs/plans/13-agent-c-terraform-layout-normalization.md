# Agent C Plan: Terraform Layout Normalization

## Mission

Normalize Terraform layout so GCP, Azure, and AWS all use the same `live/<cloud>/<environment>` root structure while keeping provider-specific modules explicit.

This is a structural refactor. It should avoid changing actual cloud resources.

## Context

Current layout is inconsistent:

```text
infra/terraform/main.tf                  # GCP root
infra/terraform/environments/dev/        # GCP backend config
infra/terraform/live/azure/dev/          # Azure root
infra/terraform/live/aws/dev/            # AWS root
infra/terraform/modules/                 # mixed GCP modules and provider-specific modules
```

Target layout:

```text
infra/terraform/
  modules/
    gcp/
    azure/
    aws/
  live/
    gcp/dev/
    azure/dev/
    aws/dev/
```

Do not create fake cloud-neutral modules.

## Files to Inspect First

```text
infra/terraform/main.tf
infra/terraform/variables.tf
infra/terraform/outputs.tf
infra/terraform/providers.tf
infra/terraform/environments/dev/*
infra/terraform/modules/*
infra/terraform/live/aws/dev/*
infra/terraform/live/azure/dev/*
.github/workflows/deploy-gcp.yml
infra/terraform/README.md
.github/copilot-instructions.md
AGENTS.md
```

## Implementation Steps

### Step 1: Inventory current GCP root files

List root-level Terraform files:

```bash
find infra/terraform -maxdepth 1 -type f -name '*.tf' -print | sort
find infra/terraform/environments/dev -maxdepth 1 -type f -print | sort
```

Identify:

- root module files
- backend config
- tfvars examples
- provider config
- outputs

Do not move `.terraform`, state files, or real local config.

### Step 2: Create GCP live root

Create:

```text
infra/terraform/live/gcp/dev/
```

Move or copy root-level GCP files into it:

```text
infra/terraform/live/gcp/dev/main.tf
infra/terraform/live/gcp/dev/variables.tf
infra/terraform/live/gcp/dev/outputs.tf
infra/terraform/live/gcp/dev/providers.tf
```

If backend config exists at:

```text
infra/terraform/environments/dev/backend.conf
```

do not commit real secrets. Prefer:

```text
infra/terraform/live/gcp/dev/backend.conf.example
```

If the existing backend file contains only non-secret bucket/path information and is already committed, move it carefully and update references. If uncertain, create an example and document required values.

### Step 3: Move GCP modules under provider namespace

Current GCP modules likely include:

```text
infra/terraform/modules/cloud-run
infra/terraform/modules/cloud-sql
infra/terraform/modules/networking
infra/terraform/modules/redis
infra/terraform/modules/storage
infra/terraform/modules/iam
infra/terraform/modules/secret-manager
infra/terraform/modules/artifact-registry
infra/terraform/modules/monitoring
```

Move them to:

```text
infra/terraform/modules/gcp/cloud-run
infra/terraform/modules/gcp/cloud-sql
infra/terraform/modules/gcp/networking
infra/terraform/modules/gcp/redis
infra/terraform/modules/gcp/storage
infra/terraform/modules/gcp/iam
infra/terraform/modules/gcp/secret-manager
infra/terraform/modules/gcp/artifact-registry
infra/terraform/modules/gcp/monitoring
```

Leave existing provider-specific modules in place:

```text
infra/terraform/modules/aws/*
infra/terraform/modules/azure/*
```

### Step 4: Update module source paths

In:

```text
infra/terraform/live/gcp/dev/*.tf
```

Update module source paths.

Example:

```hcl
source = "../../modules/cloud-run"
```

becomes:

```hcl
source = "../../../modules/gcp/cloud-run"
```

Calculate relative path from `infra/terraform/live/gcp/dev` to `infra/terraform/modules/gcp/<module>`.

From:

```text
infra/terraform/live/gcp/dev
```

to:

```text
infra/terraform/modules/gcp/cloud-run
```

the relative source is:

```hcl
source = "../../../modules/gcp/cloud-run"
```

### Step 5: Normalize outputs across cloud roots

Each cloud dev root should expose the same conceptual output names where possible:

```hcl
output "api_url" {
  value = ...
}

output "frontend_url" {
  value = ...
}

output "registry_url" {
  value = ...
}

output "api_service_name" {
  value = ...
}

output "frontend_service_name" {
  value = ...
}

output "worker_service_name" {
  value = ...
}

output "artifact_bucket" {
  value = ...
}
```

Rules:

- Prefer real values.
- If a cloud does not have an equivalent yet, output `null` with a clear description.
- Do not output secrets.
- Do not rename existing outputs if workflows depend on them unless you update those workflows.

### Step 6: Update GCP workflow Terraform path

Open:

```text
.github/workflows/deploy-gcp.yml
```

Update Terraform working directory references from:

```text
infra/terraform
```

to:

```text
infra/terraform/live/gcp/dev
```

Only change paths. Do not refactor workflow logic.

Search patterns:

```bash
grep -n "infra/terraform" .github/workflows/deploy-gcp.yml
grep -n "terraform -chdir" .github/workflows/deploy-gcp.yml
grep -n "working-directory" .github/workflows/deploy-gcp.yml
```

### Step 7: Update documentation references

Update only factual path references in:

```text
infra/terraform/README.md
.github/copilot-instructions.md
AGENTS.md
README.md
```

Document:

```text
GCP root:   infra/terraform/live/gcp/dev
Azure root: infra/terraform/live/azure/dev
AWS root:   infra/terraform/live/aws/dev
```

Do not write a large architecture essay. Keep this PR focused.

### Step 8: Remove or archive old root files

After validation, root-level GCP `.tf` files should no longer remain in:

```text
infra/terraform/
```

Allowed root-level files after refactor:

- `README.md`
- maybe `.gitignore`
- directories only

Do not leave duplicate active GCP root modules in both old and new locations.

## Validation Commands

Format:

```bash
terraform fmt -recursive infra/terraform
```

Validate:

```bash
terraform -chdir=infra/terraform/live/gcp/dev init -backend=false
terraform -chdir=infra/terraform/live/gcp/dev validate

terraform -chdir=infra/terraform/live/aws/dev init -backend=false
terraform -chdir=infra/terraform/live/aws/dev validate

terraform -chdir=infra/terraform/live/azure/dev init -backend=false
terraform -chdir=infra/terraform/live/azure/dev validate
```

Search for stale paths:

```bash
grep -R "modules/cloud-run" infra/terraform || true
grep -R "modules/cloud-sql" infra/terraform || true
grep -R "modules/networking" infra/terraform || true
grep -R "infra/terraform/environments/dev" .github README.md AGENTS.md infra/terraform/README.md docs || true
```

Expected:

- no stale GCP module source paths
- no stale GCP root path references in workflows/docs

## Acceptance Criteria

- GCP root exists at `infra/terraform/live/gcp/dev`.
- AWS, Azure, and GCP all use `infra/terraform/live/<cloud>/dev`.
- GCP modules are under `infra/terraform/modules/gcp`.
- Terraform validates for all three dev roots.
- GCP deploy workflow uses the new GCP root path.
- No Terraform state files, `.terraform` directories, or secret tfvars are committed.
- No resource behavior changes are intentionally introduced.

## Do Not Do

- Do not create generic multi-cloud modules.
- Do not change IAM permissions.
- Do not change runtime app settings unless required by moved paths.
- Do not introduce staging/prod roots in this task unless explicitly requested.
