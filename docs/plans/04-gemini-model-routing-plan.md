# Gemini model routing plan for LLM tasks

Date: 2026-05-24

This plan evaluates the current Gemini model choices for the six LLM tasks in `dachjob.ai` and defines an implementation plan for task-specific model routing. It is written for a follow-up coding agent to implement.

## Source context

- Current default Gemini fast model is `gemini-3.1-flash-lite` in `app/backend/app/core/config.py`.
- Current default Gemini reasoning model is `gemini-2.5-pro` in `app/backend/app/core/config.py`.
- `LLMGateway.run_text(...)` currently supports only a global fast model plus `reasoning=True`.
- Most business call sites do not pass a model or tier, so they use the global fast model.
- `jd_extract` has one reasoning retry path when coverage is low.

Official Gemini docs checked on 2026-05-24:

- Gemini model list: https://ai.google.dev/gemini-api/docs/models
- Gemini pricing: https://ai.google.dev/gemini-api/docs/pricing
- Supported model IDs in Gemini Interactions docs: https://ai.google.dev/gemini-api/docs/interactions

Important model notes:

- `gemini-3.5-flash` is listed as a stable Gemini 3 model and described as the most intelligent speed-oriented model.
- `gemini-3.1-flash-lite` is stable and optimized for high-volume, simple data processing.
- `gemini-3.1-pro-preview` is stronger but preview-only; use behind a canary/staging flag unless production accepts preview risk.
- `gemini-2.5-pro` is stable and still reasonable for deep reasoning fallback.
- `gemini-3-pro-preview` is deprecated and was shut down on 2026-03-09. Do not use it.
- `gemini-3.1-pro-preview-customtools` is not needed for these tasks because none of the current prompts use custom tool calling.

## Recommended model map

| Task | Current model behavior | Verdict | Recommended production model | Notes |
|---|---|---|---|---|
| `jd_format` | Fast: `gemini-3.1-flash-lite` | Mostly OK, but the workflow is risky if formatted text becomes authoritative | Keep `gemini-3.1-flash-lite`, or avoid LLM formatting for source-of-truth JD text | The task is simple formatting. The bigger risk is omission or shortening. Preserve raw JD separately and never make formatted output the only extraction input. |
| `jd_extract` initial | Fast: `gemini-3.1-flash-lite` | Borderline for quality-critical extraction | `gemini-3.5-flash` | Skill coverage, must/nice classification, DACH signals, and work authorization are core product quality. Use the stronger stable Flash model by default. |
| `jd_extract` retry | Reasoning: `gemini-2.5-pro` | Reasonable | Keep `gemini-2.5-pro` for production; optionally canary `gemini-3.1-pro-preview` | Retry volume should be low, so Pro cost is acceptable. Prefer stable 2.5 Pro unless there is a deliberate preview rollout. |
| `fit_explanation` | Fast: `gemini-3.1-flash-lite` | OK | Keep `gemini-3.1-flash-lite` | The input is already computed scores and gaps. This is short summarization, with a deterministic template fallback. |
| `resume_generate` | Fast: `gemini-3.1-flash-lite` | Not ideal | `gemini-3.5-flash`; fallback/escalation to `gemini-2.5-pro` for failures | This is long-form, user-facing, factual HTML generation for DACH applications. It benefits from stronger instruction following and factual restraint. |
| `profile_extract` | Fast: `gemini-3.1-flash-lite` | Borderline to underpowered | `gemini-3.5-flash`; fallback/escalation to `gemini-2.5-pro` for long/noisy sources | CV/LinkedIn extraction must preserve facts, dates, companies, and metrics. Imports are infrequent enough to justify the stronger model. |

Short version:

- Keep `gemini-3.1-flash-lite` for cheap/simple tasks: `jd_format`, `fit_explanation`.
- Use `gemini-3.5-flash` for quality-sensitive extraction/generation: `jd_extract` initial, `resume_generate`, `profile_extract`.
- Keep `gemini-2.5-pro` as the stable reasoning fallback for `jd_extract` retry and exceptional generation failures.
- Do not use `gemini-3-pro-preview`.
- Do not use `gemini-3.1-pro-preview-customtools` unless the product later introduces tool-calling tasks.

## Implementation plan

### 1. Add a quality model tier to configuration

Update `app/backend/app/core/config.py`.

Add:

```python
gemini_model_quality: str = "gemini-3.5-flash"
deepseek_model_quality: str = "deepseek-v4-pro"
openrouter_model_quality: str = "deepseek/deepseek-v4-pro"
```

Keep:

```python
gemini_model_fast: str = "gemini-3.1-flash-lite"
gemini_model_reasoning: str = "gemini-2.5-pro"
```

Do not edit real secrets in `.env`. If an example env file is later added, document:

```env
GEMINI_MODEL_FAST=gemini-3.1-flash-lite
GEMINI_MODEL_QUALITY=gemini-3.5-flash
GEMINI_MODEL_REASONING=gemini-2.5-pro
```

Optional staging-only experiment:

```env
GEMINI_MODEL_REASONING=gemini-3.1-pro-preview
```

### 2. Extend `LLMProvider` and `LLMGateway` for model tiers

Update `app/backend/app/modules/llm_gateway/gateway.py`.

Change `LLMProvider` to include:

```python
quality_model: str
```

Add a task-to-tier map near the gateway:

```python
TASK_MODEL_TIERS = {
    "jd_format": "fast",
    "jd_extract": "quality",
    "fit_explanation": "fast",
    "resume_generate": "quality",
    "profile_extract": "quality",
}
```

Extend `run_text(...)` with an optional tier:

```python
model_tier: str | None = None
```

Model selection order should be:

1. Explicit `model` argument.
2. `reasoning=True` -> provider reasoning model.
3. Explicit `model_tier`.
4. `TASK_MODEL_TIERS.get(task, "fast")`.
5. Provider fast model.

Expected helper shape:

```python
def _select_model(provider: LLMProvider, task: str, model: str | None, model_tier: str | None, reasoning: bool) -> str:
    if model:
        return model
    if reasoning:
        return provider.reasoning_model
    tier = model_tier or TASK_MODEL_TIERS.get(task, "fast")
    if tier == "quality":
        return provider.quality_model or provider.default_model
    if tier == "reasoning":
        return provider.reasoning_model
    return provider.default_model
```

Preserve the existing provider fallback behavior: if Gemini fails, fallback to DeepSeek/OpenRouter in configured order.

### 3. Wire quality tier into providers

Update provider builders:

- Gemini provider: `quality_model=settings.gemini_model_quality`
- DeepSeek provider: `quality_model=settings.deepseek_model_quality`
- OpenRouter provider: `quality_model=settings.openrouter_model_quality`

If backwards compatibility is needed, allow `quality_model` to fall back to `model_reasoning` or `model_fast` when missing.

### 4. Update business call sites only where explicitness helps

Because the task map should route most tasks automatically, minimal call-site changes are required.

Still make these call-site choices explicit for readability:

- In `matching/service.py`, `format_raw_jd(...)`: pass `model_tier="fast"`.
- In `matching/service.py`, first `jd_extract`: pass `model_tier="quality"` or rely on task map. Prefer explicit.
- In `matching/service.py`, retry `jd_extract`: keep `reasoning=True`.
- In `matching/service.py`, `fit_explanation`: pass `model_tier="fast"`.
- In `resumes/service.py`, `resume_generate`: pass `model_tier="quality"`.
- In `profiles/extractor.py`, `profile_extract`: pass `model_tier="quality"`.

Update `run_json(...)` to accept and forward `model_tier`.

### 5. Improve extraction validation while touching the model routing

This is not strictly required for model switching, but it makes the routing safer.

For `jd_extract`:

- Add or reuse a Pydantic output schema for parsed job posting.
- Validate JSON shape before accepting it.
- Trigger reasoning retry when:
  - JSON parsing fails.
  - Required fields are missing.
  - Combined skill count is below threshold for a long JD.
  - Responsibilities are empty for a JD with responsibility-section signals.
  - Work authorization evidence is present in raw text but missing from parsed output.

For `resume_generate`:

- Keep the existing `_ResumeOutput` schema.
- Add lightweight HTML sanity checks:
  - Output contains at least one heading and one experience/skills section.
  - Output does not contain Markdown code fences.
  - Output does not include prompt text.
  - Output has no obvious placeholder strings like `TODO`, `N/A` repeated excessively, or invented contact fields.

For `profile_extract`:

- Keep Markdown output, but add simple acceptance checks:
  - Non-empty output.
  - Contains a top-level name heading or clear profile heading.
  - Does not contain code fences or commentary.
  - Does not exceed a reasonable compression ratio suggesting copied page chrome.

### 6. Add tests

Update or add tests under `app/backend/tests/`.

Required tests:

- Gateway selects `fast` for `jd_format` and `fit_explanation`.
- Gateway selects `quality` for `jd_extract`, `resume_generate`, and `profile_extract`.
- `reasoning=True` still overrides the task tier.
- Explicit `model=...` still overrides all tiers.
- Provider fallback logs the selected model for each provider.
- `run_json(...)` forwards `model_tier`.

Recommended task tests:

- `jd_extract` low-coverage parse triggers reasoning retry.
- Invalid JSON from the quality model triggers reasoning retry or deterministic fallback.
- `resume_generate` passes `model_tier="quality"`.
- `profile_extract` passes `model_tier="quality"`.

Run at minimum:

```bash
cd app/backend
PYTHONPATH=. python3 -m pytest tests/test_llm_gateway.py tests/test_jd_format.py -v
```

If broader backend tests are stable locally, run:

```bash
cd app/backend
PYTHONPATH=. python3 -m pytest -v
```

### 7. Rollout and evaluation

Use existing `llm_runs` logging to compare models.

Track per task:

- Success/error rate.
- JSON parse/validation failure rate.
- Latency p50/p95.
- Prompt/completion token counts.
- Estimated cost.
- For `jd_extract`: skill count, responsibility count, must/nice classification quality, work authorization recall.
- For `resume_generate`: manual review score, HTML validity, hallucination count.
- For `profile_extract`: factual preservation of dates, company names, titles, education, certifications, and languages.

Suggested rollout:

1. Local smoke test with 5 representative JDs and 2 representative CV/LinkedIn sources.
2. Staging/canary with task routing enabled.
3. Review `llm_runs` after at least 20 `jd_extract`, 5 `resume_generate`, and 5 `profile_extract` calls.
4. Promote to production if quality improves without unacceptable latency/cost.
5. Roll back by setting `GEMINI_MODEL_QUALITY=gemini-3.1-flash-lite` or by reverting the task tier map.

## Acceptance criteria

- `jd_format` and `fit_explanation` still use `gemini-3.1-flash-lite` for Gemini.
- Initial `jd_extract`, `resume_generate`, and `profile_extract` use `gemini-3.5-flash` for Gemini.
- `jd_extract` reasoning retry uses `gemini-2.5-pro` unless a preview canary explicitly sets otherwise.
- `gemini-3-pro-preview` is not referenced anywhere in configuration, docs, or code.
- Existing provider fallback behavior still works.
- `llm_runs.model` records the actual selected model.
- Unit tests cover model selection and override behavior.
