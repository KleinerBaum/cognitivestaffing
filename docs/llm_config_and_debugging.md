# LLM configuration and debugging guide

This page explains how Cognitive Staffing configures OpenAI models, when to request structured JSON vs. free text, and how to debug common 400 errors (especially `response_format.schema`). It also lists the commands to reproduce extraction flows and run tests locally.

## LLM configuration & capabilities

Model routing is centralized in `config/models.py` via the `MODEL_CONFIG` map and `get_model_for` helper. Defaults favour lightweight models for extraction and reasoning models for long-form generation.

| Task | Default model | Structured output? |
| --- | --- | --- |
| Extraction (`ModelTask.EXTRACTION`) | `gpt-5.1-mini` | JSON schema via `response_format=json_schema` |
| Company info enrichment (`ModelTask.COMPANY_INFO`) | `gpt-5.1-mini` | JSON schema via `response_format=json_schema` |
| JSON repair (`ModelTask.JSON_REPAIR`) | `gpt-5.1-mini` | JSON schema via `response_format=json_schema` |
| Follow-up questions (`ModelTask.FOLLOW_UP_QUESTIONS`) | `gpt-4o` | Text only (JSON schema disabled) |
| Team advice (`ModelTask.TEAM_ADVICE`) | `gpt-4o` | Text only (JSON schema disabled) |
| Salary estimates (`ModelTask.SALARY_ESTIMATE`) | `gpt-4o-mini` | JSON schema via `response_format=json_schema` |
| Job ad / interview guide / summaries (`ModelTask.JOB_AD`, `INTERVIEW_GUIDE`, `PROFILE_SUMMARY`) | `gpt-4o` (high effort promotes to `o3-mini`; fallbacks include `gpt-3.5-turbo` and GPT-5.2 tiers) | Text with optional Markdown; no JSON schema |
| Embeddings (vector store) | `text-embedding-3-large` | Not applicable |

**Routing rules**

- **Fallback chain:** `gpt-4o-mini → gpt-4o → gpt-3.5-turbo → gpt-5.2-mini → gpt-5.2` for most chat calls; embeddings stay fixed.
- **Chat Completions vs. Responses:** GPT-4o/3.5/5 models use the Chat Completions API, while other identifiers may use Responses when allowed. The wrappers automatically drop `response_format` for tasks that opt out.
- **Reasoning effort:** Quick/cheap mode uses the lowest reasoning effort (`none`/`minimal`) on `gpt-4o-mini`; medium effort upgrades long-form generators to `gpt-4o`, and precise mode raises `REASONING_EFFORT` to route to `o3-mini` where configured.

## Response format rules (JSON schema)

When a task expects structured output, calls should set `response_format` to the JSON schema bundle constructed by `openai_utils.schemas.build_json_schema_response_format`:

- Always provide a non-empty schema name and a valid JSON Schema object under `json_schema.schema`.
- Use `strict: true` to enforce structure; schema helpers already set this flag.
- Do **not** attach `response_format` for tasks that explicitly set `allow_response_format=False` (see table above); the client will strip it automatically but upstream callers should avoid sending it.
- Keep the schema payload JSON-serializable—no `set`, `datetime`, or callable values.
- When a call is text-only, ensure `response_format` is omitted and `temperature`/`max_tokens` values are tuned for prose instead of schema repair.

## Common 400 errors and quick fixes

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `Invalid response_format.schema` | Missing `json_schema.schema` key, non-mapping payload, or unsupported field types | Rebuild the payload with `build_json_schema_response_format(name, schema)` and ensure the schema is a plain dict. |
| `This model only supports the chat/completions endpoint` | Using the Responses API with a chat-only model (`gpt-4.1*`, `gpt-5*`) | Force chat mode; the client already auto-switches, but double-check custom calls. |
| `Response format is not available for this model` | Sending `response_format` to a model or task that disallows it | Drop `response_format` (or set `use_response_format=False`) so the request falls back to text. |

### Example log patterns

A `response_format.schema` failure appears as:

```
ERROR cognitive_needs.openai: OpenAI API error (chat_completions) [session=abc step=company pipeline=extraction model=gpt-5.1-mini]: Invalid response_format.schema: expected object for json_schema.schema
```

If the model/endpoint mismatch triggers a fallback, logs show:

```
WARNING cognitive_needs.openai: response_format unsupported by primary client; retrying with chat_completions without schema (task=follow_up_questions)
```

Use these cues to confirm whether the schema payload or the chosen API mode caused the 400.

## Debugging workflow

1. **Reproduce locally**
   - Run the extraction pipeline outside Streamlit to isolate I/O and schema issues:
     ```bash
     python -m cli.extract --file path/to/job_ad.pdf --title "Data Scientist"
     ```
   - Use a `.txt` file for rapid iterations; the CLI will print the validated JSON to stdout.

2. **Enable verbose logging**
   - Streamlit: `streamlit run app.py --logger.level=debug` (shows per-task model, step, and response format decisions).
   - CLI: prefix with `PYTHONLOGLEVEL=DEBUG` to raise the global logging level while keeping contextual fields from `utils.logging_context`.

3. **Check the schema bundle**
   - If you see `response_format.schema` errors, dump the payload your call passed into the client and verify it includes `{"type": "json_schema", "json_schema": {"name": "...", "schema": {...}, "strict": true}}`.
   - Ensure the schema is compatible with the selected task (`allow_json_schema=True`).

4. **Retry without response_format** (triage)
   - Temporarily set `use_response_format=False` for the failing call; if the request succeeds in text mode, the schema payload is the culprit.
   - Restore structured mode after fixing the schema to keep outputs machine-readable.

5. **Validate against fixtures**
   - Use existing test snapshots under `tests/` (for example, integration extractions) to compare the shape of the returned JSON and spot missing keys.

## Test and validation commands

- Unit tests (default markers):
  ```bash
  poetry run pytest
  ```
- Integration tests without live LLMs:
  ```bash
  poetry run pytest --override-ini "addopts=" -m "integration and not llm"
  ```
- Live LLM coverage (requires a real `OPENAI_API_KEY`):
  ```bash
  poetry run pytest --override-ini "addopts=" -m "llm"
  ```
- Lint/format and type checks:
  ```bash
  ruff format && ruff check
  mypy --config-file pyproject.toml
  ```

## Quick checklist for new developers

- Read `config/models.py` to see which tasks allow JSON schemas and which are text-only.
- When adding a new LLM call, decide whether it needs structured JSON; prefer `response_format=json_schema` for any data that flows into `NeedAnalysisProfile`.
- Capture logs with session/step/model context (`cognitive_needs.openai` logger) when investigating 400s or retries.
- Use the CLI extractor to reproduce issues with problematic job ads before touching the UI.
