# Plan 09: Fix AWS Smoke Test 500 + HTTPS for API URL + Node.js 20 Deprecation

## Problem Statement

Three issues on the AWS deployment:

1. **Smoke test fails on `POST /api/jobs/{id}/resume` with HTTP 500** — resume generation crashes because the S3 storage client is misconfigured (uses MinIO localhost defaults instead of IAM-based S3 access). A secondary issue is that DeepSeek model names may be invalid.
2. **API URL reported as HTTP** — the deploy workflow and smoke test use the direct ALB HTTP URL (`http://dachjob-dev-alb-...`) instead of the CloudFront HTTPS URL (`https://d3ktpumdo7sly4.cloudfront.net`).
3. **Node.js 20 deprecation warnings** — `aws-actions/configure-aws-credentials@v4` targets Node.js 20 which is deprecated on GitHub Actions runners. Every step using this action emits a warning that clutters the workflow logs.

## Root Cause Analysis

### Issue 1: S3 Storage Misconfiguration

The resume endpoint (`POST /api/jobs/{id}/resume`) calls `generate_resume()` which:
1. Calls the LLM gateway (DeepSeek) — this may fail due to invalid model names but is caught by try/except and falls back to template HTML
2. Uploads the HTML and PDF to S3 via `StorageService` — **this fails** because the S3 client is misconfigured

**Why S3 is broken in AWS ECS:**

| Problem | Detail |
|---------|--------|
| Wrong env var name | Terraform sets `S3_BUCKET` but pydantic-settings expects `S3_BUCKET_NAME` (field is `s3_bucket_name`) |
| Endpoint defaults to localhost | `s3_endpoint_url` defaults to `http://localhost:9000` (MinIO) and is never overridden in ECS |
| Credentials default to MinIO | `s3_access_key_id` defaults to `minioadmin`, `s3_secret_access_key` defaults to `minioadmin` |
| IAM role is ignored | `_init_s3()` always passes explicit endpoint_url and credentials to boto3, preventing IAM task role usage |

**Why only resume fails (not parse/match):** Parse and match store results in PostgreSQL only. Resume is the only operation that uploads files to S3.

**Secondary: DeepSeek model names**

Config defaults are `deepseek-v4-flash` and `deepseek-v4-pro`. These need verification against the actual DeepSeek API. If invalid, the LLM call fails but is caught — it doesn't directly cause the 500 but means resumes always use the template fallback.

### Issue 2: API URL is HTTP

- A CloudFront distribution (`d3ktpumdo7sly4.cloudfront.net`) already exists with the ALB as origin
- The ALB routes `/api/*` → API target group, `/*` → Frontend target group
- Both API and frontend are already accessible via HTTPS through CloudFront
- But the GitHub repo variable `AWS_API_URL` and deploy workflow still reference the direct ALB HTTP URL
- CORS_ORIGINS in the ECS task definition also references the HTTP ALB URL

### Issue 3: Node.js 20 Deprecation in GitHub Actions

The `aws-actions/configure-aws-credentials@v4` action targets Node.js 20. GitHub deprecated Node.js 20 on Actions runners (see [announcement](https://github.blog/changelog/2025-09-19-deprecation-of-node-20-on-github-actions-runners/)). The env var `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` is already set in the workflow, which forces the action to run on Node 24 but emits a deprecation warning on every invocation.

The `deploy-aws.yml` workflow uses this action **8 times** (terraform, build-api, build-frontend, build-worker, deploy-api, deploy-frontend, deploy-worker, smoke-test), resulting in 8 warnings per run.

Other actions in the workflow are already Node 24 compatible:
- `actions/checkout@v6` ✅
- `actions/setup-python@v6` ✅
- `docker/login-action@v4` ✅ (v4 uses Node 24)
- `docker/setup-buildx-action@v4` ✅ (v4 uses Node 24)
- `docker/build-push-action@v7` ✅
- `hashicorp/setup-terraform@v4` ✅ (v4 uses Node 24)

## Implementation Plan

### Step 1: Fix S3 env var name in Terraform

**File:** `infra/terraform/modules/aws/ecs/main.tf`

In the API task definition container environment (around line 289), change:
```hcl
# Before:
{ name = "S3_BUCKET", value = var.artifacts_bucket_name },
# After:
{ name = "S3_BUCKET_NAME", value = var.artifacts_bucket_name },
```

In the Worker task definition container environment (around line 372), make the same change:
```hcl
# Before:
{ name = "S3_BUCKET", value = var.artifacts_bucket_name },
# After:
{ name = "S3_BUCKET_NAME", value = var.artifacts_bucket_name },
```

### Step 2: Fix StorageService to use IAM role on AWS

**File:** `app/backend/app/modules/storage/service.py`

Replace the `_init_s3` method to conditionally use explicit creds (local dev) vs IAM role (cloud):

```python
def _init_s3(self, settings) -> None:
    import boto3
    from botocore.config import Config

    kwargs: dict = {
        "config": Config(signature_version="s3v4"),
        "region_name": settings.aws_region or "eu-west-1",
    }

    # Use explicit endpoint/creds only for local development (MinIO)
    use_local = (
        settings.app_env == "local"
        or (settings.s3_endpoint_url and "localhost" in settings.s3_endpoint_url)
    )
    if use_local:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
        kwargs["aws_access_key_id"] = settings.s3_access_key_id
        kwargs["aws_secret_access_key"] = settings.s3_secret_access_key

    self._s3_client = boto3.client("s3", **kwargs)
```

### Step 3: Add `aws_region` to Settings

**File:** `app/backend/app/core/config.py`

Add the `aws_region` field near the other AWS/S3 fields (after `s3_secret_access_key`, around line 54):

```python
aws_region: str = ""
```

### Step 4: Set APP_ENV in ECS task definitions

**File:** `infra/terraform/modules/aws/ecs/main.tf`

In the API task definition environment list (around line 282), confirm `ENVIRONMENT` is already set (it is as `var.environment` which is `"dev"`). The config field `app_env` maps to env var `APP_ENV`. Add:

```hcl
{ name = "APP_ENV", value = var.environment },
```

Add this to both the API and Worker container environment blocks.

Note: `ENVIRONMENT` is already set but that doesn't map to the `app_env` field. The pydantic field is `app_env` which expects `APP_ENV`.

### Step 5: Verify DeepSeek model names

Check the DeepSeek API documentation for the current valid model IDs. As of the latest docs, valid models are typically:
- `deepseek-chat` (general purpose)
- `deepseek-reasoner` (reasoning)

If the configured defaults (`deepseek-v4-flash`, `deepseek-v4-pro`) are invalid, update in:

**File:** `app/backend/app/core/config.py` (lines 35-39)

```python
# Update to valid DeepSeek model names:
deepseek_model_fast: str = "<correct-fast-model>"
deepseek_model_quality: str = "<correct-quality-model>"
deepseek_model_reasoning: str = "<correct-reasoning-model>"
```

**Verification method:** Run `curl https://api.deepseek.com/models -H "Authorization: Bearer $DEEPSEEK_API_KEY"` using the API key from AWS Secrets Manager (`dachjob-dev/deepseek-api-key`).

### Step 6: Update GitHub repo variable for API URL

Set the `AWS_API_URL` repository variable to the CloudFront HTTPS URL:

```bash
gh variable set AWS_API_URL --body "https://d3ktpumdo7sly4.cloudfront.net"
```

This ensures:
- Smoke test hits the HTTPS endpoint
- Deployment summary shows the correct URL
- Password reset commands use HTTPS

### Step 7: Set cloudfront_domain in Terraform variables

**File:** `infra/terraform/live/aws/dev/variables.tf`

Change the default for `cloudfront_domain`:

```hcl
variable "cloudfront_domain" {
  description = "CloudFront distribution domain name"
  type        = string
  default     = "d3ktpumdo7sly4.cloudfront.net"
}
```

### Step 8: Fix CORS origins to use CloudFront domain

**File:** `infra/terraform/live/aws/dev/main.tf` (line 166)

Update the CORS origins fallback to reference the CloudFront domain:

```hcl
# Before:
cors_origins = var.cors_origins != "" ? var.cors_origins : "http://${var.name_prefix}-alb-*.elb.amazonaws.com,http://localhost:3000"

# After:
cors_origins = var.cors_origins != "" ? var.cors_origins : "https://${var.cloudfront_domain},http://localhost:3000"
```

### Step 9: Update AWS_FRONTEND_URL repo variable (if needed)

Verify that `AWS_FRONTEND_URL` is already set to the CloudFront HTTPS URL:

```bash
gh variable set AWS_FRONTEND_URL --body "https://d3ktpumdo7sly4.cloudfront.net"
```

### Step 10: Upgrade aws-actions/configure-aws-credentials to v6

**File:** `.github/workflows/deploy-aws.yml`

Replace all 8 occurrences of:
```yaml
uses: aws-actions/configure-aws-credentials@v4
```
with:
```yaml
uses: aws-actions/configure-aws-credentials@v6
```

These are on lines: 209, 295, 358, 418, 485, 672, 791, 856.

**Breaking changes in v6 (from v4):**
- Requires GitHub Actions runner v2.327.1+ (all `ubuntu-latest` and `ubuntu-24.04` runners meet this)
- No parameter changes — the `role-to-assume`, `aws-region`, and `role-session-name` inputs remain the same
- If the workflow uses `aws-access-key-id`/`aws-secret-access-key` inputs (it doesn't — it uses OIDC), those still work

**Also remove the env var workaround** at the top of the workflow (line 69):
```yaml
# Before:
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true

# After: remove this line (no longer needed once all actions target Node 24 natively)
```

**Note:** The GCP and Azure workflows (`deploy-gcp.yml`, `deploy-azure.yml`) do NOT use `aws-actions/configure-aws-credentials`, so they are unaffected. Their actions (`google-github-actions/auth@v3`, `docker/*@v4`) already target Node 24.

## Files Changed Summary

| File | Change |
|------|--------|
| `infra/terraform/modules/aws/ecs/main.tf` | Fix `S3_BUCKET` → `S3_BUCKET_NAME`; add `APP_ENV` env var |
| `app/backend/app/modules/storage/service.py` | Use IAM role on AWS, MinIO creds only for local dev |
| `app/backend/app/core/config.py` | Add `aws_region` field; potentially fix DeepSeek model names |
| `infra/terraform/live/aws/dev/variables.tf` | Set `cloudfront_domain` default |
| `infra/terraform/live/aws/dev/main.tf` | Fix CORS origins to use CloudFront |
| `.github/workflows/deploy-aws.yml` | Upgrade `aws-actions/configure-aws-credentials` v4 → v6; remove `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24` |
| GitHub repo variables | `AWS_API_URL` and `AWS_FRONTEND_URL` → `https://d3ktpumdo7sly4.cloudfront.net` |

## Deployment Steps

1. Apply code changes (steps 1–5, 7–8, 10)
2. Set GitHub repo variables (steps 6, 9)
3. Deploy with: `target=all`, `smoke_test_mode=full`
4. Verify smoke test passes all checks including `POST /api/jobs/{id}/resume`
5. Verify both URLs in the deployment summary show `https://`
6. Verify no Node.js 20 deprecation warnings in the workflow log

## Validation

After deployment, manually verify:
```bash
# Health check via HTTPS
curl -fsS https://d3ktpumdo7sly4.cloudfront.net/api/health

# Resume generation (requires auth token)
curl -X POST https://d3ktpumdo7sly4.cloudfront.net/api/jobs/{job_id}/resume \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" -d '{}'
```

## Risk Assessment

- **Low risk:** Env var rename (`S3_BUCKET` → `S3_BUCKET_NAME`) — only affects AWS, no other cloud uses this var
- **Low risk:** StorageService change — only affects S3 path; GCS and Azure Blob paths unchanged; local dev still uses MinIO via `app_env == "local"` check
- **Low risk:** CORS and URL changes — switching from HTTP ALB to HTTPS CloudFront (same backend)
- **Low risk:** `aws-actions/configure-aws-credentials` v4 → v6 — no parameter changes; OIDC-based auth works identically; only the Node.js runtime changes
- **Medium risk:** DeepSeek model names — needs verification against live API before changing defaults
