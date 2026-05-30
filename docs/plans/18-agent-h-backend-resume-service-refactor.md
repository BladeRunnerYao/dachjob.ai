# Agent H Plan: Backend Resume Service Refactor

## Mission

Split the resume generation service into prompt building, HTML rendering, PDF rendering, artifact persistence, and orchestration.

This is a backend-only refactor in the resumes domain.

## Context

The current file:

```text
app/backend/app/modules/resumes/service.py
```

mixes several concerns:

- prompt construction
- LLM invocation
- generated content handling
- HTML rendering
- PDF generation
- storage upload
- artifact persistence
- status updates

The goal is to make resume generation easier to test and change without altering API behavior.

## Files to Inspect First

```text
app/backend/app/modules/resumes/service.py
app/backend/app/modules/resumes/routes.py
app/backend/app/modules/resumes/schemas.py
app/backend/app/modules/resumes/repository.py
app/backend/app/modules/storage/service.py
app/backend/app/modules/llm_gateway/
app/backend/tests/
```

Search usage:

```bash
grep -R "resumes.service\|generate_resume\|ResumeService\|resume artifact" app/backend/app app/backend/tests
```

## Target Structure

```text
app/backend/app/modules/resumes/
  service.py               # orchestration
  prompt_builder.py
  renderer_html.py
  renderer_pdf.py
  artifacts.py
```

## Implementation Steps

### Step 1: Identify public API

Find all imports from `resumes/service.py`:

```bash
grep -R "from .*resumes.service import\|import .*resumes.service" app/backend/app app/backend/tests
```

Record public functions/classes:

- service class names
- generation functions
- artifact helpers
- exceptions/constants

These must remain compatible.

### Step 2: Classify current code

Read `service.py` and classify:

| Logic | Target file |
|---|---|
| prompt construction | `prompt_builder.py` |
| LLM call orchestration | keep in `service.py` unless tightly reusable |
| HTML string/template generation | `renderer_html.py` |
| PDF rendering/conversion | `renderer_pdf.py` |
| storage upload and artifact metadata | `artifacts.py` |
| public service orchestration | `service.py` |

Do not change prompt wording unless absolutely necessary to move code.

### Step 3: Extract prompt builder

Create:

```text
app/backend/app/modules/resumes/prompt_builder.py
```

Move prompt construction logic into functions such as:

```py
def build_resume_prompt(...args...) -> str:
    ...
```

or:

```py
class ResumePromptBuilder:
    ...
```

Prefer functions unless the current code already uses a class.

Rules:

- preserve exact prompt text
- preserve ordering of sections
- preserve tenant/profile/job context usage
- do not add prompt tuning

### Step 4: Extract HTML renderer

Create:

```text
app/backend/app/modules/resumes/renderer_html.py
```

Move logic that turns generated resume data/content into HTML.

Target shape:

```py
def render_resume_html(...args...) -> str:
    ...
```

Rules:

- keep HTML output stable
- keep CSS/styling stable
- do not redesign resume template

### Step 5: Extract PDF renderer

Create:

```text
app/backend/app/modules/resumes/renderer_pdf.py
```

Move PDF generation logic.

Target shape:

```py
def render_resume_pdf(html: str) -> bytes:
    ...
```

Rules:

- keep current PDF library
- keep current options/page size/margins
- surface errors the same way as before

Do not swallow PDF errors silently.

### Step 6: Extract artifact persistence

Create:

```text
app/backend/app/modules/resumes/artifacts.py
```

Move logic for:

- object storage key naming
- upload to storage service
- artifact metadata construction
- DB artifact persistence if currently in service

Target shape:

```py
async def persist_resume_artifacts(...args...) -> ResumeArtifact:
    ...
```

or sync if current implementation is sync.

Rules:

- generated storage paths must not change
- returned artifact shape must not change
- tenant scoping must be preserved

### Step 7: Keep service as orchestration layer

After extraction, `service.py` should read like:

```text
load profile/job context
build prompt
call LLM gateway
render HTML
render PDF
persist artifacts
return response
```

Keep route-facing public functions/classes in `service.py`.

### Step 8: Update tests or add focused tests

Look for existing resume tests:

```bash
find app/backend/tests -type f | grep -i resume
```

If coverage is weak, add tests for:

1. prompt builder preserves key sections
2. HTML renderer includes required content
3. artifact key generation is stable
4. service orchestration with mocked LLM/storage

Do not call live LLM providers.
Do not require real object storage.

## Validation Commands

Run:

```bash
cd app/backend
pip install -e ".[dev]"
ruff check app/modules/resumes tests
ruff format --check app/modules/resumes tests
pytest tests/ -k "resume or resumes" -v
pytest tests/ --ignore=tests/test_provider_smoke.py -v
```

Search:

```bash
grep -R "from .*resumes.service import" app/backend/app app/backend/tests
```

Ensure imports still resolve.

## Acceptance Criteria

- `service.py` is orchestration-focused.
- Prompt construction lives in `prompt_builder.py`.
- HTML rendering lives in `renderer_html.py`.
- PDF rendering lives in `renderer_pdf.py`.
- Artifact persistence lives in `artifacts.py`.
- Existing API behavior is preserved.
- Resume-related tests pass.
- Full backend tests pass excluding live provider smoke tests.
- No frontend, Terraform, Dockerfile, or workflow files changed.

## Do Not Do

- Do not tune prompts.
- Do not change resume templates visually.
- Do not change storage key format unless required by existing bug.
- Do not replace the PDF library.
