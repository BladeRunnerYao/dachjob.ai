# Multi-Cloud Deployment Plan: Azure First, AWS Next

## Status

Plan only. Do not implement all cloud changes in one pass.

Baseline checked from latest `origin/main` on 2026-05-25:

- Current branch for this plan: `codex/multicloud-azure-deployment-plan`
- Baseline commit: `b8b3221556bb`
- Current app shape: FastAPI API, Next.js frontend, Celery worker, Postgres, Redis, object storage, and centralized LLM gateway.

## Goals

1. Add Azure deployment support without breaking the current GCP deployment.
2. Keep backend and frontend business code as cloud-neutral as possible.
3. Make the deployment pipeline selectable by cloud: `gcp`, `azure`, and later `aws`.
4. Keep Terraform modular so adding AWS later is additive, not another rewrite.
5. Keep LLM provider selection behind the existing gateway instead of leaking cloud-specific model calls into business modules.

## Key Answer: Must Azure Use Azure AI Instead of Vertex AI?

No, it is not technically mandatory.

If the containers run on Azure, they can still call Google Gemini API or Vertex AI over public APIs if credentials are configured. That is useful for migration or fallback, but it creates cross-cloud auth, egress, latency, and operational complexity.

Recommended policy:

- On GCP, default to `LLM_PROVIDER=vertex_ai` or `LLM_PROVIDER=gemini`.
- On Azure, default to `LLM_PROVIDER=azure_openai`.
- On AWS, default later to `LLM_PROVIDER=bedrock` or an OpenAI-compatible provider.
- Allow cross-cloud fallback only through the existing provider chain, never by adding provider-specific code to jobs, profiles, resumes, matching, or tracker modules.

Business modules should keep calling `LLMGateway.run_text()` and `LLMGateway.run_json()` only.

## Current Cloud Coupling Found

### Application Layer

The application is already partly cloud-neutral:

- Backend and worker share the same Dockerfile.
- Frontend is a Dockerized Next.js app.
- LLM calls are centralized in `app/backend/app/modules/llm_gateway/gateway.py`.
- Redis is configured through `REDIS_URL`.
- Most database connections can work through `DATABASE_URL`.

Cloud-specific application points to clean up:

- `LLMGateway` currently knows `vertex_ai`, `gemini`, `deepseek`, and `openrouter`, but not `azure_openai` or `bedrock`.
- `StorageService` decides GCS vs S3 by checking whether `S3_ENDPOINT_URL` contains `storage.googleapis.com`. Replace this with an explicit `STORAGE_PROVIDER`.
- `get_async_database_url()` has a Cloud SQL socket branch. That is fine for GCP, but Azure and AWS should use plain `DATABASE_URL`.

### Infrastructure Layer

The current Terraform root under `infra/terraform` is GCP-specific:

- networking
- Artifact Registry
- Cloud SQL
- Memorystore
- GCS
- Secret Manager
- Cloud Run
- GKE
- Cloud Monitoring

The current GitHub Actions deploy workflow is also GCP-specific:

- Hardcoded workflow name and concurrency group.
- Hardcoded project, region, Cloud Run URLs, GKE cluster, Redis IP, bucket, and service accounts.
- Uses Google OIDC, Artifact Registry login, `gcloud run deploy`, Cloud Run jobs, and GKE commands directly.
- Terraform backend is GCS-specific.

## Target Service Mapping

| Capability | Current GCP | Azure target | AWS target later |
| --- | --- | --- | --- |
| API container | Cloud Run | Azure Container Apps | ECS Fargate service |
| Frontend container | Cloud Run | Azure Container Apps | ECS Fargate service or App Runner |
| Worker container | GKE Deployment | Azure Container Apps worker app or Container Apps Job | ECS Fargate worker service |
| Container registry | Artifact Registry | Azure Container Registry | ECR |
| Postgres | Cloud SQL Postgres | Azure Database for PostgreSQL Flexible Server | RDS PostgreSQL |
| Redis | Memorystore | Azure Cache for Redis | ElastiCache Redis |
| Object storage | GCS | Azure Blob Storage | S3 |
| Secrets | Secret Manager | Key Vault | Secrets Manager |
| LLM native option | Vertex AI / Gemini | Azure OpenAI | Bedrock |
| Logs/metrics | Cloud Logging/Monitoring | Log Analytics + Application Insights | CloudWatch |
| Terraform state | GCS backend | Azure Storage backend | S3 backend plus DynamoDB lock |

## Desired Runtime Environment Contract

Every cloud deployment should configure the same application-level variables wherever possible:

```env
APP_ENV=production
DATABASE_URL=...
REDIS_URL=...
REDIS_ENABLED=true
CORS_ORIGINS=...

STORAGE_PROVIDER=s3|gcs|azure_blob
STORAGE_BUCKET_NAME=...
S3_ENDPOINT_URL=...
S3_ACCESS_KEY_ID=...
S3_SECRET_ACCESS_KEY=...
AZURE_STORAGE_CONNECTION_STRING=...
AZURE_STORAGE_CONTAINER_NAME=...

LLM_PROVIDER=vertex_ai|gemini|azure_openai|deepseek|openrouter|bedrock
LLM_FALLBACK_PROVIDERS=...

JWT_SECRET=...
SECRET_KEY=...
RESEND_API_KEY=...
```

Provider-specific variables should be optional and only used when the selected provider requires them:

```env
VERTEX_AI_PROJECT_ID=...
VERTEX_AI_LOCATION=...

GEMINI_API_KEY=...
GEMINI_BASE_URL=...

AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_API_VERSION=...
AZURE_OPENAI_MODEL_FAST=...
AZURE_OPENAI_MODEL_QUALITY=...
AZURE_OPENAI_MODEL_REASONING=...

AWS_REGION=...
AWS_BEDROCK_MODEL_FAST=...
AWS_BEDROCK_MODEL_QUALITY=...
AWS_BEDROCK_MODEL_REASONING=...
```

Do not hardcode these values inside Terraform modules or GitHub workflow shell commands. Pass them from Terraform outputs, GitHub environment variables, or cloud secret stores.

## Implementation Phases

### Phase 1: Make Application Config Explicit

Scope: small backend changes, no business module changes.

1. Add settings in `app/backend/app/core/config.py`:
   - `storage_provider`
   - `storage_bucket_name`
   - `azure_storage_connection_string`
   - `azure_storage_container_name`
   - `azure_openai_api_key`
   - `azure_openai_endpoint`
   - `azure_openai_api_version`
   - `azure_openai_model_fast`
   - `azure_openai_model_quality`
   - `azure_openai_model_reasoning`
   - optional `llm_fallback_providers`

2. Refactor `app/backend/app/modules/storage/service.py`:
   - Replace URL substring detection with `STORAGE_PROVIDER`.
   - Keep existing GCS behavior for `STORAGE_PROVIDER=gcs`.
   - Keep existing S3/MinIO behavior for `STORAGE_PROVIDER=s3`.
   - Add Azure Blob support for `STORAGE_PROVIDER=azure_blob`.
   - Add unit tests with fake clients or monkeypatching; do not require live Azure.

3. Extend `app/backend/app/modules/llm_gateway/gateway.py`:
   - Add `_build_azure_openai_provider(settings)`.
   - Keep provider output as the existing `LLMProvider` dataclass.
   - Add `azure_openai` to ordered provider selection.
   - Keep `run_text()` and `run_json()` signatures unchanged.
   - Add unit tests mirroring the existing provider ordering tests.

4. Update provider smoke tests:
   - Add optional Azure OpenAI smoke config.
   - Keep the rule that the suite passes if at least one configured provider is healthy.
   - Do not require Azure credentials for normal CI.

5. Leave database code mostly unchanged:
   - GCP keeps `CLOUD_SQL_CONNECTION_NAME`.
   - Azure and AWS set `DATABASE_URL` directly and leave `CLOUD_SQL_CONNECTION_NAME` empty.

Acceptance:

- `cd app/backend && pytest tests/test_llm_gateway.py -v`
- New storage unit tests pass without cloud credentials.
- Local Docker Compose still works with MinIO and the existing `.env`.

### Phase 2: Add Azure Terraform Beside GCP

Do not move the existing GCP Terraform root in the first Azure PR. Keep it working.

Add this structure:

```text
infra/terraform/live/
  azure/
    dev/
      backend.conf.example
      main.tf
      outputs.tf
      providers.tf
      terraform.tfvars.example
      variables.tf

infra/terraform/modules/azure/
  container-apps/
  container-registry/
  key-vault/
  monitoring/
  networking/
  postgres/
  redis/
  storage/
```

Azure dev should provision:

1. Resource group.
2. Virtual network and subnets.
3. Log Analytics workspace.
4. Azure Container Registry.
5. Azure Database for PostgreSQL Flexible Server.
6. Azure Cache for Redis.
7. Storage account and blob container for artifacts.
8. Key Vault with empty application secrets.
9. User-assigned managed identity for container apps.
10. Container Apps Environment.
11. API Container App.
12. Frontend Container App.
13. Worker Container App with min replicas 1 for Celery.
14. Optional Container Apps Job for migrations.

Important Azure notes:

- Verify the selected Azure PostgreSQL version supports the `vector` extension before deployment. The first migration runs `CREATE EXTENSION IF NOT EXISTS vector`.
- For dev, public ingress plus strict app auth can be acceptable. For production, use private endpoints, locked-down firewall rules, and custom domains.
- Use Key Vault references or Container Apps secrets; do not commit secret values.
- Prefer managed identity for Azure resources where possible. Connection strings are acceptable for the first dev deployment if documented and stored in Key Vault.

Terraform outputs should include:

```text
api_url
frontend_url
acr_login_server
resource_group_name
container_app_environment_name
postgres_host
redis_hostname
storage_account_name
storage_container_name
key_vault_name
```

Acceptance:

- `terraform fmt -check -recursive infra/terraform/live/azure infra/terraform/modules/azure`
- `terraform -chdir=infra/terraform/live/azure/dev init -backend=false`
- `terraform -chdir=infra/terraform/live/azure/dev validate`
- `terraform plan` works with a real `terraform.tfvars` that is not committed.

### Phase 3: Make CI/CD Cloud-Selectable

Create a new workflow or refactor the existing one into a cloud-selectable workflow:

```yaml
workflow_dispatch:
  inputs:
    cloud:
      type: choice
      options: [gcp, azure, aws]
    environment:
      type: choice
      options: [dev, staging, prod]
    target:
      type: choice
      options: [all, api, frontend, worker, terraform]
    terraform_apply:
      type: boolean
    run_migrations:
      type: boolean
```

Use GitHub Environments:

```text
gcp-dev
azure-dev
aws-dev
```

Store cloud-specific non-secret values in GitHub environment variables and credentials in GitHub environment secrets.

Authentication:

- GCP: keep Workload Identity Federation with `google-github-actions/auth`.
- Azure: use `azure/login` with GitHub OIDC federated credentials.
- AWS: use `aws-actions/configure-aws-credentials` with an assumed IAM role.

Registry and image naming:

- GCP: Artifact Registry.
- Azure: ACR.
- AWS: ECR.
- Keep image names consistent: `api`, `frontend`, `worker`.
- Build backend once for API and worker if possible, then tag it for both workloads.

Frontend build nuance:

- Current `app/frontend/Dockerfile` bakes `NEXT_PUBLIC_API_BASE_URL` at build time.
- For Azure and AWS first deploys, the API URL may only be known after Terraform creates the service.
- Recommended first implementation:
  1. Run Terraform to create/update infrastructure.
  2. Read `api_url` from Terraform output.
  3. Build frontend with `NEXT_PUBLIC_API_BASE_URL=${api_url}`.
  4. Deploy frontend image.
- Later, consider a runtime frontend config endpoint if a single immutable frontend image must run in every cloud.

Deployment commands should live in scripts instead of growing one huge YAML file:

```text
infra/deploy/scripts/
  build-image.sh
  deploy-gcp.sh
  deploy-azure.sh
  deploy-aws.sh
  run-migrations-gcp.sh
  run-migrations-azure.sh
  run-migrations-aws.sh
```

Pipeline behavior:

1. Validate backend tests.
2. Resolve selected `cloud`, `environment`, and `target`.
3. Authenticate to the selected cloud only.
4. Run Terraform for the selected cloud only when requested.
5. Build and push selected images to the selected cloud registry.
6. Deploy selected workloads to the selected cloud runtime.
7. Run migrations as a one-off cloud-native job/task when requested.
8. Health check API and frontend URLs.
9. Write a summary with cloud, environment, image tags, URLs, and Terraform result.

Acceptance:

- Manual workflow shows `cloud` choice.
- GCP path still deploys the existing dev environment.
- Azure path can deploy API, frontend, worker, and migrations independently.
- `target=terraform` does not build or deploy app images.
- `target=api` does not redeploy frontend or worker.

### Phase 4: Normalize GCP After Azure Works

Only after Azure dev deploy works:

1. Move or wrap existing GCP Terraform into the same `infra/terraform/live/gcp/dev` shape.
2. Keep backwards-compatible README instructions during transition.
3. Replace hardcoded GCP env values in `.github/workflows/deploy.yml` with GitHub Environment vars or Terraform outputs.
4. Parameterize GCP `LLM_PROVIDER`, model names, storage provider, and secret names.
5. Decide whether to keep the worker on GKE or move it to a Cloud Run worker pattern. Current GKE worker can stay if it remains operational.

Acceptance:

- Existing GCP deploy still works after the directory normalization.
- Azure deploy continues to work.
- The workflow uses the same top-level inputs for both clouds.

### Phase 5: Add AWS

Add this structure later:

```text
infra/terraform/live/aws/dev/
infra/terraform/modules/aws/
  container-registry/
  ecs/
  iam/
  networking/
  postgres/
  redis/
  secrets/
  storage/
  monitoring/
```

AWS target:

1. ECR for images.
2. ECS Fargate services for API, frontend, and worker.
3. RDS PostgreSQL with pgvector support verified.
4. ElastiCache Redis.
5. S3 artifact bucket.
6. Secrets Manager.
7. CloudWatch logs.
8. ALB or App Runner for public ingress.
9. ECS RunTask for migrations.
10. Optional Bedrock provider in `LLMGateway`.

Acceptance:

- `cloud=aws` path can run Terraform, deploy API/frontend/worker, run migrations, and health check.
- AWS deploy does not require Azure or GCP credentials.

## Recommended Deepseek Task Order

Give Deepseek these tasks in separate PR-sized chunks:

1. Application provider cleanup:
   - Add explicit `STORAGE_PROVIDER`.
   - Add Azure Blob storage adapter.
   - Add Azure OpenAI provider to the LLM gateway.
   - Add tests.

2. Azure Terraform:
   - Add Azure Terraform modules and `live/azure/dev`.
   - Add examples only, no real secret values.
   - Add Azure deployment README.

3. Cloud-selectable workflow:
   - Add `cloud` and `environment` inputs.
   - Add cloud-specific auth, registry login, Terraform directory selection, deploy scripts, and summary.
   - Preserve the current GCP behavior.

4. GCP normalization:
   - Move or wrap GCP into the same `live/gcp/dev` pattern.
   - Remove hardcoded project/service values from workflow where possible.

5. AWS implementation:
   - Add AWS Terraform modules and workflow path.
   - Add Bedrock provider only if needed; otherwise use DeepSeek/OpenRouter/OpenAI-compatible provider first.

## Guardrails

- Do not rewrite business modules to know about Azure, AWS, or GCP.
- Do not remove the current GCP deployment path while adding Azure.
- Do not commit `.tfvars`, backend configs with real state buckets, cloud credentials, or generated `tfplan` files.
- Do not require live cloud credentials for normal unit tests.
- Keep local Docker Compose working with Postgres, Redis, and MinIO.
- Keep CORS explicit per environment.
- Keep migration execution explicit and visible in the pipeline.
- Prefer additive modules over large Terraform moves until one Azure deployment has succeeded.

## Review Checklist After Deepseek Implements

1. Backend tests pass locally.
2. New provider tests do not require real Azure credentials.
3. `STORAGE_PROVIDER=s3` still works with local MinIO.
4. `STORAGE_PROVIDER=gcs` still works for GCP.
5. `LLM_PROVIDER=vertex_ai` still works on GCP.
6. `LLM_PROVIDER=azure_openai` can be configured without changing business modules.
7. Terraform format and validate pass for Azure.
8. Workflow can select `cloud=gcp` and `cloud=azure`.
9. GCP deploy path is not regressed.
10. No secret values or generated Terraform plans are committed.
