# Error handling and fallback flows

This document explains the custom exception types, user-facing messages, and fallback behaviour used across the OpenAI-powered pipelines.

## Exception taxonomy

| Exception | When it is raised | Notes |
| --- | --- | --- |
| `NeedAnalysisPipelineError` | Base class for pipeline failures. Carries optional `step`, `model`, `schema`, `details`, and `original` exception metadata. | Provides a consistent error surface for upstream handlers. |
| `SchemaValidationError` | The model rejects or cannot honour the provided JSON schema (e.g., invalid `response_format` payload). | Marks caller bugs or schema drift; retries stop immediately. |
| `LLMResponseFormatError` | The model returns malformed or unparsable output for a schema-enforced call. | Includes the raw content when available for debugging. |
| `ExternalServiceError` | Upstream dependency failures (OpenAI network/rate limits or other services). | `details.service` identifies the dependency. |
| `LLMTimeoutError` | An OpenAI request exceeds the configured timeout. | Exposes `timeout_seconds` and the affected `service`. |

【F:openai_utils/errors.py†L1-L35】

## User-facing messages for common failures

OpenAI errors are normalised into bilingual messages before being wrapped in the domain exceptions above:

- Missing API key alerts are surfaced before dispatching any calls and block further processing. 【F:openai_utils/api.py†L101-L129】
- Network/connection issues → "Netzwerkfehler … / Network error …". 【F:openai_utils/api.py†L132-L135】
- Timeouts → "⏳ … länger als erwartet / This is taking longer than usual …". 【F:openai_utils/api.py†L136-L139】
- Invalid requests (schema errors, prompt too long) → "❌ Interner Fehler … / ❌ An internal error …". 【F:openai_utils/api.py†L140-L143】
- Rate limits or authentication errors are converted into user-friendly variants before being raised. 【F:openai_utils/api.py†L111-L118】【F:openai_utils/api.py†L1366-L1433】

## Standard fallback chains

### Core chat/extraction calls

All chat-style calls (including structured extraction and follow-ups) are made through `call_chat_api`, which enforces the following sequence:

1. **Primary attempt (Responses API).** Build a payload with schema and tool settings, then call the Responses endpoint using the preferred model. 【F:openai_utils/api.py†L1584-L1612】
2. **Model failover.** If the current model is unavailable, rotate through configured fallback models before giving up. 【F:openai_utils/api.py†L1597-L1695】
3. **Responses → Chat fallback.** On schema rejection or other OpenAIErrors, retry via Chat Completions once (or twice in classic mode) using an automatically converted payload. 【F:openai_utils/api.py†L1613-L1665】
4. **JSON repair and chat retry.** When schema-enforced outputs cannot be parsed, attempt JSON repair; if it fails, retry once more through Chat Completions with the same schema to recover structured data. 【F:openai_utils/api.py†L1717-L1746】
5. **Escalation.** Unrecoverable cases raise the mapped domain exceptions with user-friendly messages, stopping further retries. 【F:openai_utils/api.py†L1747-L1753】【F:openai_utils/api.py†L1416-L1444】

### Extraction pipeline (NeedAnalysis)

- Structured extraction relies on the sequence above. When the LLM is disabled (no API key) the pipeline immediately returns a heuristic profile without calling OpenAI. 【F:openai_utils/extraction.py†L633-L640】
- After successful parsing, heuristics backfill missing company and contact fields so downstream steps stay usable even if the model skipped values. 【F:openai_utils/extraction.py†L800-L815】

Resulting flow (Responses → Chat → heuristics):
- Responses API with JSON schema
- ↳ Chat Completions retry (for API or schema issues)
- ↳ Heuristic backfill of any gaps (or full heuristic profile when LLM unavailable)

### Follow-up question generation

- Primary call uses `call_chat_api` with optional file-search tools and a JSON schema.
- Any exception is caught and logged; the UI receives an empty `questions` list so the wizard can continue without blocking the user. 【F:pipelines/followups.py†L56-L95】

### Practical examples

- **Schema rejected by Responses:** a `SchemaValidationError` is raised immediately; if the payload can be re-expressed for Chat Completions, the client retries there before surfacing the error. 【F:openai_utils/api.py†L1613-L1654】
- **Timeout during extraction:** the timeout is converted to `LLMTimeoutError` with the friendly timeout message, and the caller can choose whether to retry or fall back to heuristics. 【F:openai_utils/api.py†L1366-L1422】

## Maintenance notes

- When adding new exception types or changing retry/fallback behaviour, update this document so contributors can predict outcomes in failure scenarios.
- Keep user-facing error strings bilingual and aligned with the mappings above whenever new OpenAI error modes are handled.
