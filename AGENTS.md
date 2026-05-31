# AGENTS.md

Instructions for AI coding assistants working on this project.

## Merge Rules

1. **Never merge until all CI jobs pass.** Do not merge a PR just because the Validate step is green — wait for all build, deploy, and smoke-test jobs to complete successfully. Never use `--admin` to bypass required status checks.

2. **Never merge without explicit permission.** After creating a PR, do not merge it yourself. Present the PR link and wait for the user to explicitly request a merge.

3. **Monitor CI and fix failures.** After pushing changes or creating a PR, actively watch all three workflow runs (deploy-gcp.yml, deploy-azure.yml, and deploy-aws.yml). If any job fails, investigate and fix the issue. Keep fixing until all jobs are green. Deploy failures on main are your responsibility to resolve.

## General Guidelines

- **Run pre-commit before testing.** Always run `pre-commit run --all-files` before running any test suite or pushing changes for review. Fix any issues found before proceeding to tests.
- Use `git worktree` for changes — create a feature branch from main in a separate worktree, make changes there, then PR back to main.
- The platform deploys to Google Cloud, Azure, and AWS. Changes to CI workflows, Terraform, or deployment scripts may affect all three clouds.
- Azure deployments sometimes experience transient OIDC federation failures (`No subscriptions found` during `az login`). The deploy workflow already includes retry logic for this.
- Deploy workflows currently use the dev Terraform roots even though workflow inputs expose `staging` and `prod`. Treat staging/prod as requiring separate backend state, GitHub Environments, variables, and secrets before production use.

## Cloud Architectures

| Service | GCP | Azure | AWS |
|---|---|---|---|
| API | Cloud Run | Container Apps | ECS Fargate (ALB) |
| Frontend | Cloud Run | Container Apps | ECS Fargate (ALB) |
| Worker | GKE Autopilot | Container Apps | ECS Fargate |
| Database | Cloud SQL (PG 16) | PostgreSQL Flexible Server | RDS PostgreSQL (pgvector) |
| Redis | Memorystore | Azure Cache for Redis | ElastiCache |
| Storage | GCS | Blob Storage | S3 |
| Registry | Artifact Registry | ACR | ECR |
| Secrets | Secret Manager | Key Vault | Secrets Manager |
| CI Auth | WIF | Azure AD OIDC | IAM OIDC |
| Terraform State | GCS bucket | Azure Storage blob | S3 bucket + DynamoDB lock |

## Environment Model

| Cloud | Terraform root used by deploy workflow | Deploy workflow | Implemented environment |
|---|---|---|---|
| GCP | `infra/terraform/live/gcp/dev/` | `deploy-gcp.yml` | dev |
| Azure | `infra/terraform/live/azure/dev/` | `deploy-azure.yml` | dev |
| AWS | `infra/terraform/live/aws/dev/` | `deploy-aws.yml` | dev |

Terraform roots for `staging` and `prod` exist under each cloud in `infra/terraform/live/`, but they are not fully wired to dedicated CI variables/secrets in the current workflows.

## AWS Details

AWS operational references live here and in `infra/terraform/README.md`.

**Authentication** — use the `dachjob-admin` IAM profile (AdministratorAccess):
```bash
export AWS_PROFILE=dachjob-admin
aws sts get-caller-identity
```

| Item | Value |
|---|---|
| Account ID | `755545427549` |
| Region | `eu-west-1` (Ireland) |
| ECS Cluster | `dachjob-dev-cluster` |

**Endpoints:**

| Service | URL |
|---|---|
| ALB (HTTP) | `dachjob-dev-alb-1730467011.eu-west-1.elb.amazonaws.com` |
| CloudFront (HTTPS) | `d3ktpumdo7sly4.cloudfront.net` |
| API (public) | `https://d3ktpumdo7sly4.cloudfront.net/api/health` |
| Frontend (public) | `https://d3ktpumdo7sly4.cloudfront.net` |
| RDS | `dachjob-dev-postgres-b682.cfsmow8y4er3.eu-west-1.rds.amazonaws.com:5432` |
| ElastiCache | `dachjob-dev-redis.k1t1ty.0001.euw1.cache.amazonaws.com:6379` |

**ECS Services:**

| Service | Desired count |
|---|---|
| `dachjob-dev-api` | 1 |
| `dachjob-dev-frontend` | 1 |
| `dachjob-dev-worker` | 0 (disabled) |

**Terraform State:**
- Bucket: `dachjob-dev-terraform-state` (S3, versioned, encrypted)
- Lock table: `dachjob-dev-terraform-lock` (DynamoDB)
- Config: `infra/terraform/live/aws/dev/`

**Terraform roots:**
- GCP dev: `infra/terraform/live/gcp/dev/`
- Azure dev: `infra/terraform/live/azure/dev/`
- AWS dev: `infra/terraform/live/aws/dev/`

**Password reset** — use the workflow dispatch input `reset_password_for` (calls the API forgot-password → reset-password flow). Or manually via curl:
```bash
# 1. Get reset token
curl -sS -X POST "${API_URL}/api/auth/forgot-password" \
  -H "Content-Type: application/json" -d '{"email":"user@example.com"}'
# 2. Extract token from reset_link, then:
curl -sS -X POST "${API_URL}/api/auth/reset-password" \
  -H "Content-Type: application/json" -d '{"token":"...","new_password":"NewPass123!"}'
```
