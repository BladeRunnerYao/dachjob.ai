# Agent F Plan: Backend Jobs Importer Refactor

## Mission

Split the large jobs importer into focused modules while preserving current behavior and public imports.

This is a backend-only refactor in the jobs domain.

## Context

The current file:

```text
app/backend/app/modules/jobs/importer.py
```

is large and mixes several responsibilities:

- fetching job pages
- detecting job source / ATS
- parsing provider-specific pages
- generic HTML extraction
- normalizing job fields
- persisting jobs
- handling import errors

The goal is to make it easier to maintain and test without changing import behavior.

## Files to Inspect First

```text
app/backend/app/modules/jobs/importer.py
app/backend/app/modules/jobs/routes.py
app/backend/app/modules/jobs/service.py
app/backend/app/modules/jobs/repository.py
app/backend/app/modules/jobs/schemas.py
app/backend/tests/
```

Search usage:

```bash
grep -R "importer\|import_job\|JobImporter\|from .*jobs.importer" app/backend/app app/backend/tests
```

## Target Structure

```text
app/backend/app/modules/jobs/
  importer.py              # compatibility facade or thin orchestrator
  import_service.py        # import orchestration
  fetcher.py               # HTTP fetch and URL handling
  normalizer.py            # canonical field normalization
  html_extractor.py        # generic HTML extraction
  ats/
    __init__.py
    greenhouse.py
    linkedin.py
    bmw.py
```

Only create ATS modules that correspond to actual logic currently present in `importer.py`. If there are other ATS-specific branches, create modules for those too.

## Implementation Steps

### Step 1: Identify public API

Before editing, identify what other code imports from `importer.py`.

Run:

```bash
grep -R "from app.modules.jobs.importer\|from \\.importer\|import .*importer" app/backend/app app/backend/tests
```

Write down:

- function names
- class names
- constants
- exceptions

These must continue to work after the refactor.

### Step 2: Classify functions in `importer.py`

Read the file and classify every function/class into one of these categories:

| Category | Target file |
|---|---|
| HTTP fetch, URL validation, redirects, user-agent handling | `fetcher.py` |
| Generic HTML title/company/location/body extraction | `html_extractor.py` |
| Source/ATS-specific parsing | `ats/<provider>.py` |
| Data cleanup, salary/location normalization, field defaults | `normalizer.py` |
| DB persistence and service orchestration | `import_service.py` |
| Backward-compatible exports | `importer.py` |

Do not create a repo file with this classification; it is working notes only.

### Step 3: Extract fetcher

Create:

```text
app/backend/app/modules/jobs/fetcher.py
```

Move logic related to:

- HTTP client/session setup
- request headers
- timeout
- redirects
- response status handling
- returning raw HTML/text

Keep behavior identical:

- same timeout
- same exception types if public
- same user agent if currently set
- same retry behavior if any

Example target shape:

```py
async def fetch_job_page(url: str) -> str:
    ...
```

or keep sync if current implementation is sync. Do not convert sync to async unless the current importer is already async.

### Step 4: Extract generic HTML extractor

Create:

```text
app/backend/app/modules/jobs/html_extractor.py
```

Move generic parsing logic:

- title extraction
- company extraction
- location extraction
- description/body extraction
- metadata extraction
- JSON-LD parsing if generic

Keep provider-specific parsing out of this file.

Target shape:

```py
def extract_job_from_html(html: str, source_url: str | None = None) -> RawJobData:
    ...
```

If no existing dataclass exists, do not introduce a large new type system. Use current dict/schema structures.

### Step 5: Extract ATS-specific parsers

Create directory:

```text
app/backend/app/modules/jobs/ats/
```

Create:

```text
app/backend/app/modules/jobs/ats/__init__.py
```

Move provider-specific logic into modules.

Examples:

```text
ats/greenhouse.py
ats/linkedin.py
ats/bmw.py
```

Each module should expose a small function such as:

```py
def parse_greenhouse_job(html: str, url: str) -> dict:
    ...
```

or whatever matches current structures.

Do not create a heavy plugin registry unless current code already resembles one. A simple dispatch function is enough.

### Step 6: Extract normalizer

Create:

```text
app/backend/app/modules/jobs/normalizer.py
```

Move logic for:

- trimming strings
- normalizing company/title/location
- normalizing salary if present
- setting defaults
- converting parser output into repository/service input

Keep behavior stable.

If current importer depends on Pydantic schemas, reuse those schemas rather than inventing new DTOs.

### Step 7: Extract orchestration into import service

Create:

```text
app/backend/app/modules/jobs/import_service.py
```

This module should express the flow:

```text
validate URL
fetch page
detect source
parse source-specific or generic
normalize
persist
return result
```

Keep database calls where they currently belong if moving them would cause broad changes. If repository already handles DB writes, call repository from here.

### Step 8: Preserve `importer.py` compatibility

After moving logic, keep `importer.py` as either:

- a thin facade that imports and re-exports public symbols, or
- a small orchestration wrapper if callers expect this file

Example:

```py
from .import_service import import_job_from_url

__all__ = ["import_job_from_url"]
```

If tests or routes import private functions from `importer.py`, either:

- keep compatibility exports, or
- update tests/callers only when safe

### Step 9: Add focused tests if missing

Look for existing tests:

```bash
find app/backend/tests -type f -name '*job*' -o -name '*import*'
```

If there are no focused importer tests, add minimal tests for:

1. source detection
2. generic HTML extraction
3. one ATS parser
4. normalization

Use small inline HTML fixtures in tests. Do not call real external URLs.

## Validation Commands

Run from backend:

```bash
cd app/backend
pip install -e ".[dev]"
ruff check app/modules/jobs tests
ruff format --check app/modules/jobs tests
pytest tests/ -k "job or importer or import" -v
pytest tests/ --ignore=tests/test_provider_smoke.py -v
```

If `app/modules/jobs` path does not work because package root differs, use:

```bash
ruff check app/app/modules/jobs tests
```

only after verifying actual backend path.

Search for stale references:

```bash
grep -R "from .*jobs.importer import" app/backend/app app/backend/tests
```

Ensure imports still resolve.

## Acceptance Criteria

- `importer.py` is no longer a large mixed-responsibility file.
- Fetching, generic extraction, ATS parsing, normalization, and orchestration are separated.
- Public imports remain compatible.
- No external network calls are added to tests.
- Jobs/importer-related tests pass.
- Full backend test suite passes excluding live provider smoke tests.
- No frontend, Terraform, Dockerfile, or workflow changes.

## Do Not Do

- Do not change job import behavior intentionally.
- Do not redesign the jobs repository schema.
- Do not introduce a plugin framework unless needed by existing code.
- Do not add live network tests.
