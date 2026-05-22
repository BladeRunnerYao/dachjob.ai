# Requirement 08: Application Tracker and Autofill Demo

## Owner Agent

Tracker and Autofill Agent

## Goal

Track applications and provide a safe autofill demo that prepares application data but never submits applications automatically.

## Tracker Statuses

Use canonical statuses:

- `Evaluated`
- `Applied`
- `Responded`
- `Interview`
- `Offer`
- `Rejected`
- `Discarded`
- `SKIP`

## Tracker Features

- Create application record from job.
- Store match score.
- Store recommendation.
- Link generated resume artifact.
- Update status.
- Add notes.
- Set next action date.

## API Endpoints

### List Applications

`GET /api/applications`

### Create Application

`POST /api/applications`

Input:

```json
{
  "job_id": "uuid",
  "resume_artifact_id": "uuid",
  "status": "Evaluated",
  "notes": "Strong AI platform fit."
}
```

### Update Application

`PATCH /api/applications/{application_id}`

Input:

```json
{
  "status": "Applied",
  "notes": "Submitted manually through company site.",
  "next_action_at": "2026-06-01T09:00:00Z"
}
```

## Autofill Demo Scope

MVP should not build a real Chrome Web Store extension. Instead:

1. Create a local mock application form page.
2. Generate autofill payload from candidate profile and selected job.
3. Fill fields in the mock page.
4. Stop before Submit.

## Mock Form Fields

- First name
- Last name
- Email
- Phone
- Location
- LinkedIn
- Work authorization
- Current employer
- Years of experience
- Resume upload field or resume link
- Cover note
- Screening question answers

## Safety Requirement

The UI must clearly show:

```text
Review required. dachjob.ai does not submit applications automatically.
```

No code path should automatically click a submit button on third-party sites.

## Acceptance Criteria

- Applications can be listed and updated.
- Tracker displays linked job and generated CV.
- Mock autofill payload can be generated.
- Mock application form can be populated.
- Submit remains manual and disabled or clearly separated in demo.

## Implementation Plan

1. Implement application routes.
2. Implement tracker repository and schemas.
3. Add tracker page integration.
4. Build mock application form page.
5. Build autofill payload generator.
6. Add UI warning and manual-review state.
7. Add tests for status validation.
