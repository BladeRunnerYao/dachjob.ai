# Raw JD Formatting, Swiss Work Authorization, and Docker Names

## Changes Overview

Improves the job detail Raw JD view so it keeps the original job description content while presenting it in a cleaner structured layout. Adds Swiss work authorization detection for citizenship, EU/EFTA, permit, right-to-work, and visa sponsorship restrictions. Updates the local Docker Compose setup and documentation to use the current image/container names with cached builds by default.

## User-Facing Changes

- Raw JD content is preserved rather than summarized or reconstructed from parsed fields.
- Raw JD text is formatted into readable sections such as overview, responsibilities, skills, benefits, seniority, employment type, job function, and industries.
- LinkedIn-style single-line job descriptions can now expose inline headings into separate sections.
- Swiss jobs display a `Swiss market` badge in the job description view.
- Swiss jobs with explicit restrictions display a top warning, including the exact evidence sentence.
- The warning covers examples such as:
  - Swiss/EU/EFTA citizenship requirements
  - Existing Swiss/EU/EFTA work authorization requirements
  - No visa sponsorship or unsupported non-EU candidates

## Backend Changes

### `app/backend/app/modules/matching/service.py`

- Added Swiss location detection for Switzerland, Swiss, Schweiz, Suisse, Svizzera, Zurich, Zuerich, Zürich, Geneva, Basel, Bern, and Lausanne.
- Added strict work authorization regex patterns for citizenship, passport, work permit, right-to-work, EU/EFTA, and non-EU support restrictions.
- Added visa sponsorship warning patterns.
- Added `_extract_work_authorization()` to return structured `status`, `label`, `detail`, and `evidence`.
- Added work authorization enrichment into `parsed_json["work_authorization"]`.
- Added `dach_signals["work_authorization"]` when an authorization signal is detected.
- Updated the JD parsing prompt so LLM extraction can include `work_authorization`.

## Frontend Changes

### `app/frontend/src/components/jobs/job-description-view.tsx`

- Removed LinkedIn noise filtering that could remove original Raw JD content.
- Added formatting that preserves raw text but detects headings and list-like sections.
- Added inline heading splitting for LinkedIn descriptions where section headings appear inside a long paragraph.
- Added support for numbered and bullet-style list items.
- Added visual badges for `formatted raw JD` and `Swiss market`.
- Added top-of-page Swiss work authorization alert with evidence.
- Added frontend fallback detection for Swiss authorization restrictions even when older parsed JSON lacks `work_authorization`.
- Added section styling for responsibilities, benefits, requirements, summaries, and language-related sections.

## Docker and Local Runtime Changes

### `infra/docker/docker-compose.yml`

- Updated API image and container name to `dachjob-backend-api`.
- Updated worker image and container name to `dachjob-backend-worker`.
- Updated frontend image name to `dachjob-frontend`.

### Documentation

- Documented that local Docker builds should use:

```bash
docker-compose -f infra/docker/docker-compose.yml up -d --build
```

- Documented that cached Docker builds are the default.
- Documented that `--no-cache` should only be used when explicitly requested.
- Updated Docker Compose references in README and implementation docs from `docker compose` to `docker-compose`.

## Verification

- Rebuilt and started the Docker Compose stack with cached builds.
- Confirmed running containers:
  - `dachjob-backend-api`
  - `dachjob-backend-worker`
  - `dachjob-frontend`
- Confirmed API health via `/api/health`.
- Logged in with the Tiyao Li account.
- Verified the Digitec Raw JD keeps original content and displays structured sections.
- Verified the Optiml Swiss/EU citizenship restriction appears as a top warning with exact evidence.
- Verified job tabs still work:
  - Raw JD
  - Parsed Requirements
  - Match Score
  - Evidence Mapping
  - Generated CV
- Verified main navigation still works:
  - Dashboard
  - Profile Vault
  - Jobs
  - Tracker
  - LLM Runs
- Ran targeted frontend lint:

```bash
npx eslint src/components/jobs/job-description-view.tsx
```

- Ran backend syntax check:

```bash
python3 -m py_compile app/backend/app/modules/matching/service.py
```
