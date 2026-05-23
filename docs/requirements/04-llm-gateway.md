# Requirement 04: LLM Gateway and DeepSeek Integration

## Owner Agent

LLM Platform Agent

## Goal

Build a centralized LLM gateway that wraps DeepSeek API, logs every LLM run, validates structured outputs, and keeps model/provider details out of business modules.

## DeepSeek Configuration

Use OpenAI-compatible SDK:

- `DEEPSEEK_BASE_URL=https://api.deepseek.com`
- Fast model: `deepseek-v4-flash`
- Reasoning model: `deepseek-v4-pro`

Do not hardcode API keys.

## Gateway Responsibilities

1. Accept task name, tenant context, prompt version, messages, model preference, and output schema.
2. Call DeepSeek through the OpenAI SDK.
3. Measure latency.
4. Capture token usage if returned.
5. Store one row in `llm_runs`.
6. Validate structured output with Pydantic.
7. Return parsed output or typed error.

## Business Modules Must Not

- Directly instantiate `OpenAI`.
- Directly read `DEEPSEEK_API_KEY`.
- Store prompt text in random module files.
- Trust raw LLM output without validation.

## Prompt Storage

Recommended structure:

```text
app/backend/app/modules/llm_gateway/prompts/
  jd_extract.v1.md
  fit_explanation.v1.md
  evidence_select.v1.md
  resume_generate.v1.md
  screening_answer.v1.md
```

## Core API

```python
class LLMGateway:
    def run_json(
        self,
        tenant_id: UUID,
        task: str,
        prompt_version: str,
        messages: list[dict],
        output_schema: type[BaseModel],
        model: str | None = None,
        thinking: bool = False,
    ) -> BaseModel:
        ...
```

## LLM Tasks

| Task | Model | Output Schema |
|---|---|---|
| `jd_extract` | `deepseek-v4-flash` | `ParsedJobPosting` |
| `fit_explanation` | `deepseek-v4-pro` | `FitExplanation` |
| `evidence_select` | `deepseek-v4-flash` | `EvidenceSelection` |
| `resume_generate` | `deepseek-v4-pro` | `GeneratedResume` |
| `screening_answer` | `deepseek-v4-flash` | `ScreeningAnswerSet` |

## Required Schemas

### Parsed Job Posting

```json
{
  "title": "AI Platform Engineer",
  "company": "Example GmbH",
  "location": "Berlin, Germany",
  "work_model": "hybrid",
  "language_requirements": ["English", "German nice-to-have"],
  "must_have_skills": ["Python", "Kubernetes", "MLOps"],
  "nice_to_have_skills": ["Terraform", "Azure"],
  "responsibilities": ["Build ML platform services"],
  "salary_range": "not specified",
  "seniority": "Senior",
  "dach_signals": {
    "country": "Germany",
    "visa_or_work_auth": "not specified",
    "works_council_or_tariff": "not specified"
  }
}
```

## Logging Privacy

By default, `llm_runs` should not store full prompt text. Store:

- task
- model
- prompt version
- input hash
- latency
- token usage
- status
- error

For local debugging, full prompt logging may be enabled with `LLM_LOG_PROMPTS=true`, but it should be off by default in any shared environment.

## Acceptance Criteria

- DeepSeek client works with environment config.
- A fake/test LLM provider can be used in tests.
- Every LLM call creates an `llm_runs` row.
- Invalid JSON output raises a typed validation error.
- Business modules can call the gateway without knowing provider details.

## Implementation Plan

1. Implement settings for DeepSeek.
2. Implement provider interface and DeepSeek provider.
3. Implement `LLMGateway`.
4. Add prompt loader.
5. Add Pydantic schemas for each task.
6. Add LLM run logging.
7. Add unit tests with fake provider.
8. Add one integration test gated by `DEEPSEEK_API_KEY`.
