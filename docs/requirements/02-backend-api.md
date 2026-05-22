# Requirement 02: Backend API Foundation

## Owner Agent

Backend Foundation Agent

## Goal

Build the FastAPI application foundation with settings, database session wiring, tenant context, health endpoint, structured errors, and module layout.

## Required Stack

- Python 3.12+
- FastAPI
- Uvicorn
- Pydantic Settings
- SQLAlchemy
- Alembic
- Psycopg
- Celery
- Redis

## Required Structure

```text
apps/api/
  app/
    main.py
    core/
      config.py
      security.py
      tenant.py
      telemetry.py
      errors.py
    db/
      session.py
      models.py
      seed_demo.py
      migrations/
    modules/
      tenants/
      profiles/
      jobs/
      matching/
      resumes/
      llm_gateway/
      tracker/
      storage/
    workers/
      celery_app.py
      tasks.py
  pyproject.toml
  Dockerfile
```

## API Foundation Requirements

### Health Endpoint

`GET /api/health`

Response:

```json
{
  "status": "ok",
  "service": "dachjob.ai-api",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "object_storage": "ok"
  }
}
```

### Tenant Context

MVP can use a fixed local tenant from environment:

- `DEFAULT_TENANT_SLUG=dachjob-local`

Future-ready behavior:

- Read tenant from header `X-Tenant-Slug` when provided.
- Resolve tenant in dependency `get_tenant_context`.
- All module services receive tenant context explicitly.

### Error Handling

Use consistent error shape:

```json
{
  "error": {
    "code": "job_not_found",
    "message": "Job posting not found",
    "details": {}
  }
}
```

### API Prefixes

- `/api/health`
- `/api/profile`
- `/api/jobs`
- `/api/applications`
- `/api/llm-runs`
- `/api/artifacts`

## Acceptance Criteria

- FastAPI app starts locally.
- OpenAPI docs show all routers.
- Health endpoint checks DB and Redis.
- Tenant dependency works with default tenant.
- Alembic is configured.
- Celery app can be imported by worker.

## Implementation Plan

1. Initialize Python project and dependencies.
2. Implement settings in `core/config.py`.
3. Implement database engine/session.
4. Implement tenant context dependency.
5. Implement health router.
6. Register routers in `main.py`.
7. Configure Celery app.
8. Add smoke tests for health and settings.
