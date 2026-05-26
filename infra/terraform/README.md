# Cloud Infrastructure — dachjob.ai

Terraform configuration for deploying dachjob.ai on GCP and Azure.

## Architecture

See [docs/deployment/gcp-architecture.md](/docs/deployment/gcp-architecture.md) for the full architecture overview.

## Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.6
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install)
- Authenticated with: `gcloud auth application-default login`

## Quick Start

```bash
# 1. First apply (bootstrap state bucket)
cd infra/terraform
terraform init
TF_VAR_project_id=... \
TF_VAR_billing_account_id=... \
TF_VAR_notification_email=... \
terraform plan -out=tfplan
terraform apply tfplan

# 2. On subsequent runs, use the GCS backend
# Update environments/dev/backend.conf with the state bucket name from step 1
```

## Directory Structure

```
infra/terraform/
├── main.tf                    # Root module — orchestrates all submodules
├── versions.tf                # Provider and Terraform version constraints
├── backend.tf                 # GCS backend configuration
├── providers.tf               # GCP provider configuration
├── variables.tf               # Input variables
├── outputs.tf                 # Output values
├── terraform.tfvars.example   # Example variable values
│
├── modules/
│   ├── networking/            # VPC + Serverless VPC Connector
│   ├── artifact-registry/     # Docker image repositories
│   ├── cloud-sql/             # PostgreSQL + pgvector
│   ├── memorystore/           # Redis
│   ├── cloud-storage/         # GCS buckets
│   ├── secret-manager/        # Secrets (API keys, passwords)
│   ├── iam/                   # Service accounts + IAM bindings
│   ├── cloud-run/             # Cloud Run services (API + Frontend)
│   ├── gke/                   # GKE Autopilot cluster
│   └── monitoring/            # Budget alerts + uptime checks
│
└── environments/
    └── dev/
        └── backend.conf       # Dev backend config
```

## Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `project_id` | string | — | GCP project ID |
| `region` | string | `europe-west1` | GCP region |
| `environment` | string | `dev` | Environment name |
| `billing_account_id` | string | — | Billing account ID |
| `notification_email` | string | — | Email for budget/monitoring alerts |
| `db_tier` | string | `db-f1-micro` | Cloud SQL tier |
| `db_disk_size_gb` | number | `20` | Cloud SQL disk size |
| `redis_tier` | string | `basic` | Redis tier |
| `redis_memory_size_gb` | number | `1` | Redis memory size |
| `gke_machine_type` | string | `e2-custom-2-4096` | GKE machine type |
| `budget_amount` | number | `200` | Monthly budget in EUR |

## Security

**Never commit `terraform.tfvars` files.** They contain secrets (project IDs, billing accounts,
emails, passwords). Real `.tfvars` files must be:

- Created locally and kept outside version control
- Supplied by CI from GitHub Variables/Secrets

For local runs, prefer `TF_VAR_*` environment variables or an untracked local tfvars file.

The repository `.gitignore` blocks all `*.tfvars`, `*.tfstate`, `*.tfstate.*`, and `*.tfplan` files.

## CI/CD Pipeline

Deployment is split into two cloud-specific workflows:

- [`.github/workflows/deploy-gcp.yml`](/.github/workflows/deploy-gcp.yml) — GCP Cloud Run + GKE
- [`.github/workflows/deploy-azure.yml`](/.github/workflows/deploy-azure.yml) — Azure Container Apps

The old combined [`.github/workflows/deploy.yml`](/.github/workflows/deploy.yml) is deprecated
and kept for manual fallback only.

Each pipeline supports:
- **Automatic**: Push to `main` or `deploy/*` branches triggers build + deploy
- **Manual** via `workflow_dispatch`: Select branch, target (all/api/frontend/worker/terraform), and optionally run Terraform

### Required CI Variables and Secrets

GCP Terraform reads these GitHub Variables/Secrets as `TF_VAR_*` values:

- `GCP_BILLING_ACCOUNT_ID`
- `GCP_NOTIFICATION_EMAIL`

Azure Terraform reads sensitive values from Azure Key Vault after GitHub Actions authenticates
to Azure with OIDC. GitHub should only store non-sensitive Azure identifiers as repository
variables:

- Required variables: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_RESOURCE_GROUP`, `AZURE_KEY_VAULT_NAME`
- Runtime variables: `AZURE_ACR_NAME`, `AZURE_CONTAINER_APP_ENV`, `AZURE_API_NAME`, `AZURE_FRONTEND_NAME`, `AZURE_WORKER_NAME`, `AZURE_MIGRATION_JOB_NAME`, `AZURE_API_URL`, `AZURE_FRONTEND_URL`
- Optional Azure OpenAI variables: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_VERSION`, `AZURE_OPENAI_MODEL_FAST`, `AZURE_OPENAI_MODEL_QUALITY`, `AZURE_OPENAI_MODEL_REASONING`

Required Key Vault secrets:

- `postgres-administrator-password`
- `database-url`
- `redis-url`
- `azure-storage-connection-string`
- `jwt-secret`
- `secret-key`

Optional Key Vault secrets:

- `azure-openai-api-key`
- `resend-api-key`

Azure API and worker Container Apps store database, Redis, storage, Azure OpenAI, auth, and email credentials as Container Apps secrets. The Azure workflow loads Terraform and migration secrets from Key Vault instead of storing them as GitHub Secrets.

Azure migration jobs need `database-url` in Key Vault when the job does not already exist. `redis-url` and `azure-storage-connection-string` are optional and are passed as Container Apps job secrets when configured.

## Worker Mode

The worker can be enabled or disabled at deploy time via `worker_mode` workflow dispatch input.

- `worker_mode=disabled`: No worker pod deployed. API runs workflows synchronously.
  - Existing GKE cluster is kept but the worker deployment is scaled to zero.
- `worker_mode=enabled`: Worker pods deployed. API enqueues long-running workflows to Celery.

### GKE Cluster Teardown

Worker-disabled deploys scale the worker deployment to zero but do **not** destroy the GKE cluster.

If cost remains too high even with zero worker pods:
1. Implement a separate `enable_worker_infrastructure` variable in Terraform
2. Guard all `module.gke` outputs with `try(...)`
3. Update GitHub Actions so `worker_mode=enabled` requires GKE infrastructure
4. Run a separate reviewed Terraform plan before destroying the cluster
