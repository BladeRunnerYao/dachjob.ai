# Plan 17: iOS App API Connection Fix

## Problem
iOS app shows "Session expired. Please log in again." when connecting to any cloud API (Azure, GCP, AWS).

## Root Cause Analysis

1. **Server URL change doesn't clear auth token**: When the user changes the server URL in settings, the old JWT token (signed with a different server's `JWT_SECRET`) is still stored and sent. The new server rejects it → 401 → "session expired". **FIXED in this PR** — changing server URL now triggers logout.

2. **Request timeout**: The iOS app had no timeout, defaulting to 60s. Slow cloud responses cause "long wait". **FIXED in this PR** — 15s timeout added.

3. **JWT_SECRET consistency**: Each cloud deployment must have a stable `JWT_SECRET` environment variable. If the secret rotates on redeploy, existing tokens become invalid.

## Code Fixes (Already Applied)

- `ios/DachJob/Views/LoginView.swift`: `ServerSettingsView` now takes `authService` as EnvironmentObject. When the server URL changes, it calls `authService.logout()` to clear the stored token.
- `ios/DachJob/Services/APIClient.swift`: Added 15s timeout on all requests.

## Verification Steps (Requires Cloud CLI)

If the issue persists after the code fix, an agent with cloud CLI access should verify:

### 1. Check JWT_SECRET is set on each deployment

```bash
# Azure
az containerapp show --name dj-az2-api --resource-group dachjob-az2-rg \
  --query "properties.template.containers[0].env[?name=='JWT_SECRET']"

# GCP
gcloud run services describe dachjob-dev-api --region europe-west1 \
  --format "yaml(spec.template.spec.containers[0].env)" | grep JWT_SECRET

# AWS
aws ecs describe-task-definition --task-definition dachjob-dev-api \
  --query "taskDefinition.containerDefinitions[0].secrets[?name=='JWT_SECRET']"
```

### 2. Verify the API health endpoint is reachable

```bash
curl -sS https://dj-az2-api.orangeglacier-d5ea9ba9.francecentral.azurecontainerapps.io/api/health
curl -sS https://dachjob-dev-api-qxugiew36a-ew.a.run.app/api/health
curl -sS https://deaivibphzjhr.cloudfront.net/api/health
```

### 3. Test login flow

```bash
# Test against each API
for API in "https://dj-az2-api.orangeglacier-d5ea9ba9.francecentral.azurecontainerapps.io" \
           "https://dachjob-dev-api-qxugiew36a-ew.a.run.app" \
           "https://deaivibphzjhr.cloudfront.net"; do
  echo "Testing: $API"
  curl -sS -X POST "$API/api/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"test@example.com","password":"TestPass123!"}' | jq .
done
```

### 4. If JWT_SECRET is missing or changes between deploys

Set a stable secret in each cloud's secret manager:
- **Azure**: Key Vault → `jwt-secret`
- **GCP**: Secret Manager → `jwt-secret`
- **AWS**: Secrets Manager → `dachjob-dev-secrets` → `JWT_SECRET` field

Then ensure the container environment references it (check Terraform configuration in `infra/terraform/`).

## Expected Outcome

After deploying the iOS fix:
1. User opens iOS app → sees login screen (no stale token)
2. User enters server URL in settings → existing token is cleared
3. User logs in → gets fresh token from that server
4. API calls succeed with the new token
