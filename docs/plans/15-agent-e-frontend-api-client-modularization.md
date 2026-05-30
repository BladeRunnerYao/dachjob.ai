# Agent E Plan: Frontend API Client Modularization

## Mission

Split the large frontend API client into domain-specific clients while preserving public behavior.

This is a frontend-only refactor. It should not change API endpoints, backend behavior, deployment, or UI features.

## Context

The current API client is concentrated in:

```text
app/frontend/src/lib/api/client.ts
```

It contains many domains in one file, including jobs, profile, matching, resumes, background tasks, LLM runs, and mock/demo fallback behavior.

The goal is to improve maintainability without forcing large call-site changes.

## Files to Inspect First

```text
app/frontend/src/lib/api/base-client.ts
app/frontend/src/lib/api/client.ts
app/frontend/src/lib/api/
app/frontend/src/contexts/AuthContext.tsx
app/frontend/src/app/**
app/frontend/src/components/**
```

Search usage:

```bash
grep -R "apiClient\|from .*lib/api\|from .*lib/api/client" app/frontend/src
```

## Target Structure

```text
app/frontend/src/lib/api/
  base-client.ts
  jobs-client.ts
  profile-client.ts
  matching-client.ts
  resumes-client.ts
  tasks-client.ts
  llm-runs-client.ts
  mock-client.ts
  client.ts
  index.ts
```

## Implementation Steps

### Step 1: Map existing methods by domain

Open `client.ts` and create a temporary working list in your notes, not in the repo.

Classify every method:

| Domain | Example methods |
|---|---|
| Jobs | list, get, create/import, update, delete, enrich |
| Profile | get profile, update profile, extract profile |
| Matching | match job/profile, get report |
| Resumes | generate, download, list artifacts |
| Tasks | background task status/list |
| LLM runs | observability/history |
| Mock/demo | fallback data, local/demo methods |

Do not skip methods. Every existing public method must either move or remain as wrapper.

### Step 2: Create domain clients

Each domain client should extend `BaseApiClient` or accept the same request helper.

Example:

```ts
import { BaseApiClient } from "./base-client";

export class JobsClient extends BaseApiClient {
  async listJobs() {
    return this.request(...);
  }
}
```

Use existing types from `client.ts` initially. If types are embedded in `client.ts`, move them only when helpful:

- domain-specific types can move into the domain client
- shared types can stay in `client.ts` or move to `types.ts`

Avoid a giant type refactor in this PR.

### Step 3: Move methods without changing endpoint strings

For each method:

1. Copy it to the domain client.
2. Keep the same endpoint path.
3. Keep the same request body.
4. Keep the same error behavior.
5. Keep the same mock fallback behavior for now.

Do not rename endpoints.
Do not change return shapes.
Do not change auth behavior.

### Step 4: Move mock/demo logic to `mock-client.ts`

If mock functions are mixed into the production client, move them to:

```text
app/frontend/src/lib/api/mock-client.ts
```

Acceptable shape:

```ts
export const mockApi = {
  ...
};
```

or:

```ts
export class MockClient {
  ...
}
```

Then domain clients can import mock helpers if current behavior requires fallback.

Do not remove mock behavior unless tests/build prove it is unused and the product owner agrees.

### Step 5: Preserve compatibility facade

Keep:

```text
app/frontend/src/lib/api/client.ts
```

as the public facade.

If current callers do:

```ts
apiClient.getJobs()
```

then `client.ts` must still expose:

```ts
getJobs(...args) {
  return this.jobs.getJobs(...args);
}
```

If current callers do:

```ts
apiClient.jobs.getJobs()
```

preserve that too.

The safest approach is:

```ts
class ApiClient extends BaseApiClient {
  readonly jobs = new JobsClient();
  readonly profile = new ProfileClient();
  readonly matching = new MatchingClient();
  readonly resumes = new ResumesClient();
  readonly tasks = new TasksClient();
  readonly llmRuns = new LlmRunsClient();

  getJobs(...args) {
    return this.jobs.getJobs(...args);
  }
}

export const apiClient = new ApiClient();
```

Adjust constructors if `BaseApiClient` requires config.

### Step 6: Add or update `index.ts`

If missing, create:

```text
app/frontend/src/lib/api/index.ts
```

Export:

```ts
export * from "./base-client";
export * from "./client";
export * from "./jobs-client";
export * from "./profile-client";
export * from "./matching-client";
export * from "./resumes-client";
export * from "./tasks-client";
export * from "./llm-runs-client";
```

Avoid circular imports.

### Step 7: Fix imports only if necessary

Prefer not to touch many UI files.

If build fails because of import names, update call sites minimally.

Do not combine this with UI refactoring.

## Validation Commands

```bash
cd app/frontend
npm ci
npm run lint
npm run build
```

Search for broken import paths:

```bash
grep -R "from .*lib/api/client" app/frontend/src || true
grep -R "from .*lib/api" app/frontend/src || true
```

Review final file sizes:

```bash
wc -l app/frontend/src/lib/api/*.ts
```

Expected:

- `client.ts` is substantially smaller than before
- domain clients contain focused methods

## Acceptance Criteria

- API methods are grouped into domain-specific clients.
- Current public API remains compatible.
- No endpoint behavior changes.
- `npm run lint` passes.
- `npm run build` passes.
- No backend, Terraform, workflow, or Dockerfile changes.

## Do Not Do

- Do not redesign auth state.
- Do not change API endpoints.
- Do not add a new data fetching library.
- Do not remove mock behavior unless it is proven unused and safe.
