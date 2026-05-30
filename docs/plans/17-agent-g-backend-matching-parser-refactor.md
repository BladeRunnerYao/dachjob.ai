# Agent G Plan: Backend Matching JD Parser Refactor

## Mission

Split the matching job-description parser into deterministic parsing, LLM parsing, and skill extraction modules while preserving existing behavior.

This is a backend-only refactor in the matching domain.

## Context

The current parser file:

```text
app/backend/app/modules/matching/jd_parser.py
```

is large and mixes:

- deterministic/rule-based parsing
- LLM prompt construction
- LLM invocation
- LLM response parsing
- fallback behavior
- skill extraction and normalization

The goal is to make parsing behavior testable and easier to evolve.

## Files to Inspect First

```text
app/backend/app/modules/matching/jd_parser.py
app/backend/app/modules/matching/service.py
app/backend/app/modules/matching/routes.py
app/backend/app/modules/matching/schemas.py
app/backend/app/modules/llm_gateway/
app/backend/tests/
```

Search usage:

```bash
grep -R "jd_parser\|parse_jd\|parse_job_description\|extract.*skill" app/backend/app app/backend/tests
```

## Target Structure

```text
app/backend/app/modules/matching/
  jd_parser.py             # compatibility facade
  parser/
    __init__.py
    deterministic.py
    llm.py
    skills.py
    models.py              # optional, only if useful
```

## Implementation Steps

### Step 1: Identify public API

Identify every symbol imported from `jd_parser.py`.

Run:

```bash
grep -R "from .*jd_parser import\|import .*jd_parser" app/backend/app app/backend/tests
```

Record:

- public functions
- classes/dataclasses
- constants
- exception types

These must still be available after refactor.

### Step 2: Classify parser logic

Read `jd_parser.py` and classify code:

| Logic | Target module |
|---|---|
| regex/rule-based extraction | `parser/deterministic.py` |
| prompt construction | `parser/llm.py` |
| LLM gateway calls | `parser/llm.py` |
| LLM JSON cleanup/validation | `parser/llm.py` |
| skill extraction/normalization | `parser/skills.py` |
| shared result shape | `parser/models.py` or existing schemas |
| public compatibility | `jd_parser.py` |

Keep working notes outside the repo.

### Step 3: Create parser package

Create:

```text
app/backend/app/modules/matching/parser/__init__.py
```

The package should export the main parser functions needed by `jd_parser.py`:

```py
from .deterministic import parse_deterministic
from .llm import parse_with_llm
from .skills import extract_skills
```

Adjust names to match existing code.

### Step 4: Extract deterministic parser

Create:

```text
app/backend/app/modules/matching/parser/deterministic.py
```

Move logic that does not require LLM:

- section parsing
- regex extraction
- title/role inference
- requirements extraction
- language/skill keyword extraction if deterministic

This module must not import the LLM gateway.

Target shape:

```py
def parse_deterministic(description: str) -> ParsedJobDescription:
    ...
```

If current code returns a dict, keep dict return shape.

### Step 5: Extract skill helpers

Create:

```text
app/backend/app/modules/matching/parser/skills.py
```

Move:

- skill keyword lists
- normalization
- de-duplication
- categorization
- seniority/level helpers if skill-related

Target helpers:

```py
def normalize_skill(skill: str) -> str:
    ...

def extract_skills(text: str) -> list[str]:
    ...
```

Keep exact casing/normalization behavior unless tests require a fix.

### Step 6: Extract LLM parser

Create:

```text
app/backend/app/modules/matching/parser/llm.py
```

Move:

- prompt construction
- LLM gateway calls
- model tier selection if parser-specific
- response JSON parsing
- fallback handling specific to failed LLM output

Do not change provider selection or model tier behavior.

Do not duplicate LLM gateway code; call existing gateway service.

Target shape:

```py
async def parse_with_llm(description: str, tenant_context: TenantContext | None = None) -> ParsedJobDescription:
    ...
```

Match current async/sync behavior.

### Step 7: Optional shared models

Only create:

```text
parser/models.py
```

if current parser has internal dataclasses/types that are shared across deterministic and LLM modules.

Do not duplicate Pydantic schemas that already exist in `schemas.py`.

### Step 8: Keep `jd_parser.py` as facade

Refactor `jd_parser.py` to:

- import from parser modules
- expose the same public API
- orchestrate deterministic + LLM fallback if that was the previous behavior

Example:

```py
from .parser.deterministic import parse_deterministic
from .parser.llm import parse_with_llm
from .parser.skills import extract_skills
```

If callers expect `parse_job_description`, keep that function in `jd_parser.py` and delegate internally.

### Step 9: Add focused parser tests

Find existing tests:

```bash
find app/backend/tests -type f | grep -E "matching|parser|jd"
```

If coverage is weak, add tests for:

1. deterministic parsing with a short JD
2. skill extraction normalization
3. LLM parser response cleanup using a mocked gateway
4. fallback path when LLM response is invalid

Do not call live LLM providers.

## Validation Commands

Run:

```bash
cd app/backend
pip install -e ".[dev]"
ruff check app/modules/matching tests
ruff format --check app/modules/matching tests
pytest tests/ -k "matching or jd_parser or parser" -v
pytest tests/ --ignore=tests/test_provider_smoke.py -v
```

Search:

```bash
grep -R "from .*jd_parser import" app/backend/app app/backend/tests
```

Ensure public imports still resolve.

## Acceptance Criteria

- `jd_parser.py` is much smaller and serves as compatibility facade/orchestrator.
- Deterministic parsing does not import or call LLM code.
- LLM parser is isolated.
- Skill extraction helpers are isolated.
- Existing matching behavior remains compatible.
- No live provider tests are added.
- Relevant and full backend tests pass.
- No frontend, workflow, Dockerfile, or Terraform changes.

## Do Not Do

- Do not redesign matching scoring.
- Do not change model tiers.
- Do not change prompt content unless required for exact extraction.
- Do not introduce a new LLM provider abstraction.
