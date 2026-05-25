# GCP Infrastructure — dachjob.ai

Terraform configuration for deploying dachjob.ai on Google Cloud Platform.

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
terraform plan -var-file=environments/dev/terraform.tfvars -out=tfplan
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
        ├── terraform.tfvars   # Dev environment variables
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

## CI/CD Pipeline

See [.github/workflows/deploy.yml](/.github/workflows/deploy.yml) for the GitHub Actions pipeline.

The pipeline supports:
- **Automatic**: Push to `main` or `deploy/*` branches triggers build + deploy
- **Manual** via `workflow_dispatch`: Select branch, target (all/api/frontend/worker/terraform), and optionally run Terraform

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
