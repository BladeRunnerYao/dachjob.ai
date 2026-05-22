# Requirement 07: Frontend Dashboard

## Owner Agent

Frontend Agent

## Goal

Build a practical SaaS-style dashboard for the local MVP. The UI should make the product feel like an AI/Data Platform tool, not a landing page.

## Recommended Stack

- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui or a small local component system
- lucide-react for icons

## Pages

### 1. Dashboard

Path: `/`

Shows:

- Total jobs
- Apply/maybe/skip counts
- Recent jobs
- Recent generated CVs
- LLM run summary

### 2. Profile Vault

Path: `/profile`

Features:

- Paste/upload CV Markdown
- Show parsed profile summary
- Show evidence chunks
- Refresh chunks

### 3. Jobs

Path: `/jobs`

Features:

- List jobs
- Filter by status/recommendation
- Add new job by pasting JD
- Show score and status

### 4. Job Detail

Path: `/jobs/[id]`

Features:

- Raw JD tab
- Parsed requirements tab
- Match score tab
- Evidence mapping tab
- Generated CV tab

### 5. Tracker

Path: `/tracker`

Features:

- Application table
- Status update
- Notes
- Links to generated artifacts

### 6. LLM Runs

Path: `/llm-runs`

Features:

- Show model, task, status, latency, created time
- Filter by task/status
- Drill into error details

## UI Requirements

- No marketing hero page for MVP.
- First screen should be dashboard.
- Use dense, readable operational UI.
- Avoid oversized decorative cards.
- Use icons for actions where clear.
- Make job score and recommendation easy to scan.
- Make provenance visible in the job detail page.

## Mock-First Development

Frontend can start with mock data before backend endpoints are ready.

Recommended API client layer:

```text
apps/web/lib/api/
  client.ts
  jobs.ts
  profile.ts
  tracker.ts
  llm-runs.ts
```

## Acceptance Criteria

- User can navigate between all MVP pages.
- User can paste a job description.
- User can upload/paste CV.
- Job detail displays parsed requirements and match report.
- Generated CV can be previewed.
- Application status can be updated.
- UI works at desktop and mobile widths.

## Implementation Plan

1. Initialize Next.js app.
2. Create layout and navigation.
3. Build API client with mock fallback.
4. Build Dashboard page.
5. Build Profile Vault page.
6. Build Jobs list and create-job flow.
7. Build Job Detail tabs.
8. Build Tracker page.
9. Build LLM Runs page.
10. Connect to real API endpoints as they become available.
