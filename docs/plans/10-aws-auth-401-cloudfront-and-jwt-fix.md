# Plan 10: Fix AWS Auth 401 (CloudFront Header Stripping + JWT Secret Mismatch + S3 Logic Bug)

## Problem Statement

Three related issues on the AWS deployment after Plan 09:

1. **Smoke test fails on `GET /api/auth/me` with HTTP 401** — immediately after a successful register/login that returns a valid JWT token.
2. **Frontend login "flash" on AWS** — user fills email + password, clicks login, briefly sees the dashboard, then is immediately redirected back to `/login`.
3. **S3 StorageService still uses MinIO credentials on AWS** — the `use_local` logic in `_init_s3()` has a bug that always triggers the local path because `s3_endpoint_url` defaults to `http://localhost:9000`.

All three issues share a common theme: environment configuration mismatches between what Terraform injects and what the Python app expects.

## Root Cause Analysis

### Issue 1 & 2: CloudFront Strips the `Authorization` Header

**Symptom:** Any authenticated API request through CloudFront (`https://d3ktpumdo7sly4.cloudfront.net/api/*`) fails with 401, while unauthenticated endpoints (health, register, login) work fine.

**Root cause:** The CloudFront distribution `d3ktpumdo7sly4.cloudfront.net` was created manually (not managed by Terraform). Its cache behavior for the ALB origin does NOT forward the `Authorization` header to the origin. By default, CloudFront:
- Strips most headers (including `Authorization`) before forwarding to the origin
- Only forwards headers explicitly listed in the cache policy or origin request policy

**Evidence:**
- `POST /api/auth/register` works (no Authorization header needed — public route)
- `GET /api/auth/me` with `Authorization: Bearer <token>` fails (header stripped by CloudFront)
- The frontend calls `fetch('/api/auth/me', { headers: { Authorization: 'Bearer ...' } })` which goes through CloudFront → ALB → API, but the API never sees the header

**Why the frontend "flashes":**
1. Login POST succeeds → token stored in localStorage → `router.push('/')` → dashboard renders
2. `useEffect` in `AuthContext` fires → `fetch('/api/auth/me')` through CloudFront → 401
3. Catch block removes token from localStorage → `router.push('/login')`
4. User sees: dashboard flash → redirect back to login

**The smoke test previously passed** because it was hitting the ALB HTTP URL directly (before Plan 09 set `cloudfront_domain`). Now that the Terraform output resolves to `https://d3ktpumdo7sly4.cloudfront.net`, the smoke test goes through CloudFront and fails.

### Issue 3 (Secondary): JWT Secret Env Var Name Mismatch

| What Terraform sets | What pydantic-settings expects | Result |
|---|---|---|
| `JWT_SECRET_KEY` (via Secrets Manager) | `JWT_SECRET` (maps to field `jwt_secret`) | Secret is **ignored**; app uses default `"change-me-in-production"` |

The pydantic `Settings` class has field `jwt_secret: str = "change-me-in-production"` which maps to env var `JWT_SECRET`. The Terraform ECS task definition injects the Secrets Manager value as `JWT_SECRET_KEY`. With `model_config = {"extra": "allow"}`, pydantic-settings does NOT load extra env vars — only extra constructor kwargs.

**Impact:** The API signs and verifies JWTs with the hardcoded default `"change-me-in-production"`. This is:
- A **security vulnerability** (predictable/hardcoded secret in production)
- NOT the direct cause of the 401 (since both sign and verify use the same default, auth "works" within a session)
- A ticking time bomb if anyone discovers the default secret

### Issue 4: S3 `use_local` Logic Bug (from Plan 09 review)

```python
use_local = (
    settings.app_env == "local"
    or (settings.s3_endpoint_url and "localhost" in settings.s3_endpoint_url)
)
```

On AWS ECS:
- `APP_ENV` = `"dev"` (not `"local"`) ✓
- `S3_ENDPOINT_URL` is NOT set in ECS → pydantic uses the **default** `"http://localhost:9000"`
- `"localhost" in "http://localhost:9000"` → **True**
- Result: `use_local = True` even on AWS!

The service then passes `endpoint_url="http://localhost:9000"` and MinIO credentials to boto3, which will fail to connect to actual S3.

## Implementation Plan

### Step 1: Fix CloudFront to Forward Authorization Header

The CloudFront distribution needs to be configured to forward auth-related headers to the ALB origin. Two approaches:

**Option A (Recommended): Manage CloudFront in Terraform**

Create a new Terraform module `infra/terraform/modules/aws/cloudfront/` that manages the distribution as code:

**File:** `infra/terraform/modules/aws/cloudfront/main.tf`

```hcl
# Custom cache policy: no caching for API requests
resource "aws_cloudfront_cache_policy" "api_no_cache" {
  name        = "${var.name_prefix}-api-no-cache"
  min_ttl     = 0
  default_ttl = 0
  max_ttl     = 0

  parameters_in_cache_key_and_forwarded_to_origin {
    cookies_config {
      cookie_behavior = "none"
    }
    headers_config {
      header_behavior = "none"
    }
    query_strings_config {
      query_string_behavior = "all"
    }
  }
}

# Origin request policy: forward all viewer headers (including Authorization)
resource "aws_cloudfront_origin_request_policy" "forward_all_headers" {
  name = "${var.name_prefix}-forward-all-headers"

  cookies_config {
    cookie_behavior = "all"
  }
  headers_config {
    header_behavior = "allViewerAndWhitelistCloudFront"
    headers {
      items = ["CloudFront-Forwarded-Proto"]
    }
  }
  query_strings_config {
    query_string_behavior = "all"
  }
}

# Cache policy for frontend: short TTL with standard caching
resource "aws_cloudfront_cache_policy" "frontend_cache" {
  name        = "${var.name_prefix}-frontend-cache"
  min_ttl     = 0
  default_ttl = 60
  max_ttl     = 86400

  parameters_in_cache_key_and_forwarded_to_origin {
    cookies_config {
      cookie_behavior = "none"
    }
    headers_config {
      header_behavior = "none"
    }
    query_strings_config {
      query_string_behavior = "all"
    }
  }
}

resource "aws_cloudfront_distribution" "this" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = ""
  comment             = "${var.name_prefix} distribution"
  price_class         = "PriceClass_100"  # US/Europe/Israel only (cheapest)

  origin {
    domain_name = var.alb_dns_name
    origin_id   = "alb"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  # API behavior: /api/* — no caching, forward all headers
  ordered_cache_behavior {
    path_pattern     = "/api/*"
    allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "alb"

    cache_policy_id          = aws_cloudfront_cache_policy.api_no_cache.id
    origin_request_policy_id = aws_cloudfront_origin_request_policy.forward_all_headers.id

    viewer_protocol_policy = "redirect-to-https"
    compress               = true
  }

  # Default behavior: frontend — light caching
  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "alb"

    cache_policy_id          = aws_cloudfront_cache_policy.frontend_cache.id
    origin_request_policy_id = aws_cloudfront_origin_request_policy.forward_all_headers.id

    viewer_protocol_policy = "redirect-to-https"
    compress               = true
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = var.tags
}
```

**File:** `infra/terraform/modules/aws/cloudfront/variables.tf`

```hcl
variable "name_prefix" {
  type = string
}

variable "alb_dns_name" {
  type        = string
  description = "ALB DNS name to use as CloudFront origin"
}

variable "tags" {
  type    = map(string)
  default = {}
}
```

**File:** `infra/terraform/modules/aws/cloudfront/outputs.tf`

```hcl
output "distribution_id" {
  value = aws_cloudfront_distribution.this.id
}

output "domain_name" {
  value = aws_cloudfront_distribution.this.domain_name
}
```

Then wire it into `infra/terraform/live/aws/dev/main.tf`:

```hcl
module "cloudfront" {
  source = "../../modules/aws/cloudfront"

  name_prefix  = var.name_prefix
  alb_dns_name = module.ecs.alb_dns_name
  tags         = local.common_tags
}
```

And update the `cloudfront_domain` variable to reference the output:
```hcl
cloudfront_domain = module.cloudfront.domain_name
```

**Note:** Before applying, the existing manually-created distribution must be deleted or imported into Terraform state:
```bash
# Option 1: Import existing
terraform import module.cloudfront.aws_cloudfront_distribution.this <DISTRIBUTION_ID>

# Option 2: Delete existing via AWS Console, then terraform apply creates a new one
```

**Option B (Quick fix): Update CloudFront via AWS CLI**

If Option A is too much scope, fix the existing distribution manually:

```bash
# Get current config
aws cloudfront get-distribution-config --id <DIST_ID> --output json > cf-config.json

# Edit cf-config.json to:
# 1. Set the /api/* behavior's OriginRequestPolicyId to "216adef6-5c7f-47e4-b989-5492eafa7d43"
#    (AWS managed policy: AllViewerExceptHostHeader — forwards all headers including Authorization)
# 2. Set the /api/* behavior's CachePolicyId to "4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
#    (AWS managed policy: CachingDisabled — no caching for API)

# Update distribution
aws cloudfront update-distribution --id <DIST_ID> \
  --if-match <ETAG_FROM_GET> \
  --distribution-config file://cf-config-updated.json
```

The key managed policies to use:
| Behavior | Cache Policy | Origin Request Policy |
|---|---|---|
| `/api/*` | `CachingDisabled` (4135ea2d-6df8-44a3-9df3-4b5a84be39ad) | `AllViewerExceptHostHeader` (b689b0a8-53d0-40ab-baf2-68738e2966ac) |
| `Default (*)` | `CachingOptimized` or custom short-TTL | `AllViewerExceptHostHeader` (b689b0a8-53d0-40ab-baf2-68738e2966ac) |

### Step 2: Fix JWT Secret Env Var Name

**File:** `infra/terraform/modules/aws/ecs/main.tf`

Change the secret name from `JWT_SECRET_KEY` to `JWT_SECRET` in both API and Worker task definitions:

```hcl
# API secrets (around line 302):
# Before:
var.jwt_secret_arn != "" ? [{ name = "JWT_SECRET_KEY", valueFrom = var.jwt_secret_arn }] : [],
# After:
var.jwt_secret_arn != "" ? [{ name = "JWT_SECRET", valueFrom = var.jwt_secret_arn }] : [],

# Worker secrets (around line 381):
# Before:
var.jwt_secret_arn != "" ? [{ name = "JWT_SECRET_KEY", valueFrom = var.jwt_secret_arn }] : [],
# After:
var.jwt_secret_arn != "" ? [{ name = "JWT_SECRET", valueFrom = var.jwt_secret_arn }] : [],
```

**Impact:** After this change, the API will use the actual secret from Secrets Manager instead of the hardcoded default. Any existing sessions/tokens signed with the old default `"change-me-in-production"` will become invalid. This is acceptable since:
- The app is in dev/early deployment
- All tokens expire within 7 days (jwt_expire_minutes = 10080)
- Users can simply re-login

### Step 3: Fix S3 `use_local` Logic

**File:** `app/backend/app/modules/storage/service.py`

The condition should only check `app_env`, not the default value of `s3_endpoint_url`:

```python
# Before:
use_local = (
    settings.app_env == "local"
    or (settings.s3_endpoint_url and "localhost" in settings.s3_endpoint_url)
)

# After:
use_local = settings.app_env == "local"
```

**Rationale:** The `app_env` field is the authoritative indicator of the runtime environment. On AWS ECS, `APP_ENV=dev`. For local dev (Docker Compose), `APP_ENV=local` (the default). The endpoint URL check is redundant and buggy because the default value (`http://localhost:9000`) is always present unless explicitly overridden.

**Alternative (defensive):** If you want to keep supporting a scenario where someone explicitly sets `S3_ENDPOINT_URL` to a non-localhost value in local dev:

```python
use_local = settings.app_env == "local"
if not use_local and settings.s3_endpoint_url and "localhost" not in settings.s3_endpoint_url:
    # Someone explicitly set a custom S3 endpoint (e.g., LocalStack on non-localhost)
    kwargs["endpoint_url"] = settings.s3_endpoint_url
```

But the simpler approach (just check `app_env`) is recommended.

### Step 4: Add `S3_ENDPOINT_URL` override in ECS (belt-and-suspenders)

**File:** `infra/terraform/modules/aws/ecs/main.tf`

In BOTH the API and Worker task definitions, explicitly set `S3_ENDPOINT_URL` to empty string to prevent any ambiguity:

```hcl
# In API environment list (after S3_BUCKET_NAME):
{ name = "S3_ENDPOINT_URL", value = "" },

# In Worker environment list (after S3_BUCKET_NAME):
{ name = "S3_ENDPOINT_URL", value = "" },
```

This ensures even if the Step 3 code fix isn't deployed yet, the endpoint URL default won't interfere.

### Step 5: Verify `AWS_API_URL` Repo Variable

Ensure the GitHub repo variable `AWS_API_URL` is correctly set. After Step 1 (CloudFront fix), it should point to:
```
https://d3ktpumdo7sly4.cloudfront.net
```

If Step 1 uses Option A (Terraform-managed CloudFront) and creates a NEW distribution, update this variable to the new domain.

### Step 6: Add Smoke Test Direct-ALB Fallback (Optional)

To avoid coupling the smoke test to CloudFront health, add an option to test both paths:

**File:** `infra/deploy/scripts/smoke-test-api.sh`

Before the `/api/auth/me` call, add a diagnostic:
```bash
# 6a. Verify the auth token works (direct diagnostic)
info "Verifying token format: ${token:0:20}..."
```

This helps debug future token issues without exposing the full token.

## Files Changed Summary

| File | Change |
|------|--------|
| `infra/terraform/modules/aws/cloudfront/main.tf` | **NEW** — CloudFront distribution with proper header forwarding |
| `infra/terraform/modules/aws/cloudfront/variables.tf` | **NEW** — Module variables |
| `infra/terraform/modules/aws/cloudfront/outputs.tf` | **NEW** — Module outputs |
| `infra/terraform/live/aws/dev/main.tf` | Add `module "cloudfront"` block; update `cloudfront_domain` reference |
| `infra/terraform/modules/aws/ecs/main.tf` | Fix `JWT_SECRET_KEY` → `JWT_SECRET`; add `S3_ENDPOINT_URL=""` |
| `infra/terraform/modules/aws/ecs/outputs.tf` | Add `alb_dns_name` output for CloudFront module |
| `app/backend/app/modules/storage/service.py` | Simplify `use_local` to check only `app_env` |

## Deployment Steps

1. **Option A path:** Delete or import the existing CloudFront distribution into Terraform state
2. Apply Terraform changes (creates/updates CloudFront, fixes JWT secret name, adds S3_ENDPOINT_URL)
3. Deploy API service (picks up new env vars: `JWT_SECRET`, `S3_ENDPOINT_URL=""`)
4. Wait ~5 minutes for CloudFront config propagation
5. Run smoke test: `smoke_test_mode=full`
6. Verify frontend login works end-to-end

## Validation

```bash
# 1. Verify CloudFront forwards Authorization header
curl -fsS https://d3ktpumdo7sly4.cloudfront.net/api/health
# Should return {"status":"ok"}

# 2. Login and verify /me works through CloudFront
TOKEN=$(curl -fsS -X POST https://d3ktpumdo7sly4.cloudfront.net/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"pass"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")
curl -fsS https://d3ktpumdo7sly4.cloudfront.net/api/auth/me \
  -H "Authorization: Bearer ${TOKEN}"
# Should return user object, NOT 401

# 3. Verify JWT uses real secret (not default)
# After deploying with JWT_SECRET fix, old tokens should be invalidated
# Login again to get a new token signed with the real secret

# 4. Verify S3 upload works (resume generation)
curl -fsS -X POST https://d3ktpumdo7sly4.cloudfront.net/api/jobs/{job_id}/resume \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" -d '{}'
# Should NOT return 500
```

## Risk Assessment

| Change | Risk | Mitigation |
|--------|------|------------|
| CloudFront cache/origin policy | Low | API has no caching (CachingDisabled); all requests forwarded as-is |
| JWT_SECRET_KEY → JWT_SECRET rename | Medium | Invalidates all existing tokens; users must re-login. Acceptable for dev env |
| S3 `use_local` simplification | Low | Only changes behavior on non-local environments; local dev unchanged |
| S3_ENDPOINT_URL="" in ECS | Low | Belt-and-suspenders; even without code fix, boto3 ignores empty endpoint |
| Terraform-managed CloudFront | Medium | Must import or delete existing distribution first; distribution ID may change |

## Immediate Workaround (Before Full Fix)

If you need the smoke test and frontend to work immediately before implementing the full plan:

1. **Fix CloudFront manually via AWS Console:**
   - Go to CloudFront → Distributions → `d3ktpumdo7sly4.cloudfront.net`
   - Edit the `/api/*` cache behavior (or default if no path-specific behavior exists)
   - Set Cache Policy to `CachingDisabled`
   - Set Origin Request Policy to `AllViewerExceptHostHeader`
   - Save and wait for deployment (~2-5 minutes)

2. **Or bypass CloudFront in the smoke test** by setting `AWS_API_URL` repo variable to the ALB HTTP URL:
   ```bash
   gh variable set AWS_API_URL --body "http://dachjob-dev-alb-1730467011.eu-west-1.elb.amazonaws.com"
   ```
   (This is a temporary workaround — the frontend will still be broken.)