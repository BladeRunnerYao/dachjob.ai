# Requirement 05: Job Ingestion, Parsing, and Matching

## Owner Agent

Job Matching Agent

## Goal

Allow the user to create job postings from pasted JD text, parse them into structured data, calculate a deterministic fit score, and generate a human-readable explanation.

## Job Creation

Endpoint:

`POST /api/jobs`

Input:

```json
{
  "url": "https://example.com/job/123",
  "raw_jd": "Full job description text..."
}
```

Output:

```json
{
  "id": "uuid",
  "status": "new"
}
```

## JD Parsing

Endpoint:

`POST /api/jobs/{job_id}/parse`

Behavior:

1. Enqueue Celery task.
2. Task calls LLM Gateway with `jd_extract`.
3. Validate parsed output.
4. Save `parsed_json`.
5. Update job status to `parsed`.

## Match Scoring

Endpoint:

`POST /api/jobs/{job_id}/match`

The score must be deterministic first, then explained by DeepSeek.

### Score Dimensions

| Dimension | Weight | Notes |
|---|---:|---|
| Role relevance | 20% | AI/Data/Platform/MLOps relevance |
| Skill match | 25% | Must-have and nice-to-have overlap |
| Evidence strength | 20% | Retrieved CV evidence coverage |
| DACH feasibility | 15% | Germany/DACH, language, work model, location |
| Compensation fit | 10% | Salary if available |
| Growth/story value | 10% | Value for target career narrative |

### Recommendation Rules

- `>= 4.2`: `apply`
- `3.6 - 4.19`: `maybe`
- `< 3.6`: `skip`

These thresholds can be configuration later.

## Required Output

```json
{
  "overall_score": 4.3,
  "recommendation": "apply",
  "breakdown": {
    "role_relevance": 4.8,
    "skill_match": 4.4,
    "evidence_strength": 4.2,
    "dach_feasibility": 4.0,
    "compensation_fit": 3.5,
    "growth_story_value": 4.5
  },
  "top_reasons": [
    "Strong overlap with Python, Kubernetes, Kafka, and AI platform operations."
  ],
  "gaps": [
    "GCP evidence is weaker than Azure/AWS evidence."
  ]
}
```

## DACH-Specific Rules

Scoring should consider:

- Country and city
- Remote/hybrid/onsite
- German language requirement
- English-only feasibility
- EU/Germany work authorization
- Salary range when available
- Company type: product company, consultancy, automotive, startup, big tech

## Acceptance Criteria

- User can create a job with raw JD.
- User can parse the job.
- Parsed job has title, company, skills, responsibilities, location, seniority.
- Match report is saved.
- Score explanation references real parsed fields and candidate evidence.
- Jobs list can filter by recommendation and status.

## Implementation Plan

1. Implement job routes and schemas.
2. Implement job repository.
3. Implement parse Celery task.
4. Implement deterministic score calculator.
5. Implement evidence coverage helper.
6. Implement LLM explanation call.
7. Save match report.
8. Add tests for scoring with sample jobs.
