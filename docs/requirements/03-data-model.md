# Requirement 03: Data Model, Migrations, and Tenant Isolation

## Owner Agent

Data Model Agent

## Goal

Define the database schema for multi-tenant job matching, CV evidence, LLM observability, generated artifacts, and application tracking.

## Core Principle

Every business table must include `tenant_id`. MVP may enforce tenant isolation in application queries. A later version may add Postgres Row Level Security.

## Tables

### `tenants`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `slug` | text unique | e.g. `tiyao-local` |
| `name` | text | |
| `created_at` | timestamp | |

### `users`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `email` | text unique | |
| `name` | text | |
| `created_at` | timestamp | |

### `memberships`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `tenant_id` | UUID FK | |
| `user_id` | UUID FK | |
| `role` | text | `owner`, `member`, `viewer` |

### `candidate_profiles`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `tenant_id` | UUID FK indexed | |
| `full_name` | text | |
| `headline` | text | |
| `location` | text | |
| `timezone` | text | |
| `raw_cv_md` | text | canonical CV input |
| `profile_json` | jsonb | structured profile |
| `created_at` / `updated_at` | timestamp | |

### `evidence_chunks`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `tenant_id` | UUID FK indexed | |
| `profile_id` | UUID FK | |
| `source_type` | text | `cv`, `portfolio`, `story`, `manual` |
| `source_label` | text | human readable source |
| `content` | text | chunk text |
| `metadata_json` | jsonb | section, dates, tags |
| `embedding` | vector | pgvector |
| `created_at` | timestamp | |

### `job_postings`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `tenant_id` | UUID FK indexed | |
| `title` | text | |
| `company` | text | |
| `url` | text nullable | |
| `location` | text nullable | |
| `raw_jd` | text | pasted JD |
| `parsed_json` | jsonb | DeepSeek extraction |
| `status` | text | `new`, `parsed`, `matched`, `discarded` |
| `created_at` / `updated_at` | timestamp | |

### `match_reports`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `tenant_id` | UUID FK indexed | |
| `job_id` | UUID FK | |
| `overall_score` | numeric | 1.0-5.0 |
| `recommendation` | text | `apply`, `maybe`, `skip` |
| `breakdown_json` | jsonb | dimension scores |
| `gaps_json` | jsonb | missing skills/risks |
| `explanation` | text | LLM explanation |
| `created_at` | timestamp | |

### `resume_artifacts`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `tenant_id` | UUID FK indexed | |
| `job_id` | UUID FK | |
| `match_report_id` | UUID FK nullable | |
| `html_object_key` | text | MinIO key |
| `pdf_object_key` | text nullable | MinIO key |
| `provenance_json` | jsonb | bullet to source evidence mapping |
| `created_at` | timestamp | |

### `applications`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `tenant_id` | UUID FK indexed | |
| `job_id` | UUID FK | |
| `resume_artifact_id` | UUID FK nullable | |
| `status` | text | `Evaluated`, `Applied`, `Interview`, etc. |
| `score` | numeric nullable | |
| `notes` | text | |
| `next_action_at` | timestamp nullable | |
| `created_at` / `updated_at` | timestamp | |

### `llm_runs`

| Field | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `tenant_id` | UUID FK indexed | |
| `task` | text | `jd_extract`, `fit_explain`, `resume_generate` |
| `provider` | text | `deepseek` |
| `model` | text | |
| `prompt_version` | text | |
| `input_hash` | text | avoid logging full PII by default |
| `latency_ms` | integer | |
| `tokens_json` | jsonb nullable | |
| `status` | text | `success`, `error` |
| `error_message` | text nullable | |
| `created_at` | timestamp | |

## Migration Requirements

1. Create all tables with UUID primary keys.
2. Enable `vector` extension.
3. Add indexes on `tenant_id`.
4. Add indexes on common foreign keys.
5. Add vector index when embedding dimension is known.

## Demo Seed Requirements

`python -m app.db.seed_demo` should create:

- Tenant `tiyao-local`
- Demo user
- Candidate profile
- Sample evidence chunks
- 2-3 sample DACH job postings

## Acceptance Criteria

- Alembic migration runs cleanly.
- Tables exist with tenant_id.
- Seed script can be run repeatedly without duplicating tenant.
- Basic query by tenant works.
- pgvector extension is active.

## Implementation Plan

1. Define SQLAlchemy models.
2. Configure Alembic autogeneration.
3. Create initial migration.
4. Implement seed script.
5. Add repository/helper functions that always filter by tenant.
6. Add tests for tenant isolation on two sample tenants.
