# Refactoring targets: OpenAI client + ingestion heuristics

This document captures the two largest remaining monoliths and proposes how to split them into testable, focused components. The goal is to mirror the recent wizard flow refactor (state sync + section helpers) and make isolated changes safer to validate.

## `openai_utils/api.py` (≈2400 lines)

**Current responsibilities (examples)**
- Schema building and validation for structured calls (`build_schema_format_bundle`, `build_need_analysis_json_schema_payload`).
- Request assembly, retry envelopes, and model fallback routing for both Responses and classic chat (`call_chat_api` and helpers).
- Tool execution loops plus usage accounting for streaming/non-streaming responses.
- UI error surfacing and feature gating (API-key banners, Streamlit alerts).

**Proposed split**
1. **Client/core transport** (`openai_utils/client_core.py`): encapsulate session creation, base URL selection, and retry/backoff decisions. Provide a minimal `send_request` that accepts a normalized payload and returns a typed `RawOpenAIResponse` with usage metadata.
2. **Request builders** (`openai_utils/request_builders.py`): translate high-level calls into transport-ready payloads. Separate builders for schema-first calls vs. free-form prompts, plus adapters for Responses→Chat fallbacks (ensuring `response_format` and `strict` flags are normalized once).
3. **Tool orchestration** (`openai_utils/tools_runner.py`): execute tool functions, merge tool call messages back into the conversation, and expose a small interface `ToolRunResult` so the caller can continue the loop without depending on Streamlit.
4. **Response parsing/validation** (`openai_utils/response_parser.py`): extract text/usage/tool calls/file-search results, handle streaming completion detection, and normalise usage counters. This module should be unit-testable without network calls.
5. **Orchestrator facade** (`openai_utils/client.py` or `openai_utils/chat_client.py`): a high-level `OpenAIClient` that wires builders + transport + parser to deliver the current `ChatCallResult` shape. Keep the comparison/AB-runner isolated here so retry logic stays single-purpose.

**Migration notes**
- Start by moving pure helpers (schema formatting, usage normalisation, streaming completion checks) into parser/builder modules while keeping `call_chat_api` as a thin wrapper. Once parity tests pass, replace the legacy entrypoints with the orchestrator class.
- Add focused tests for the parser (usage aggregation, tool-call extraction, streaming fallbacks) to decouple from HTTP fixtures.

## `ingest/heuristics.py` (≈2800 lines)

**Current responsibilities (examples)**
- Contact + location extraction regexes and HR-line parsing.
- Team/management hints, reporting lines, and remote/onsite percentages.
- Skill bucketing, deduplication, and soft/hard classifiers.
- Salary parsing, travel/time allocation heuristics, and benefits fillers.

**Proposed split**
1. **Contact & location heuristics** (`ingest/heuristics_contacts.py`): email/phone/url/name extraction, HR-line pairing, city/postcode detection, and normalisation helpers.
2. **Role context & logistics** (`ingest/heuristics_role.py`): reporting lines, team structure, travel expectations, remote/onsite parsing, start-date/availability cues.
3. **Skills & requirements** (`ingest/heuristics_skills.py`): hard/soft/tool/language classification, deduplication, and ESCO-aligned mapping hooks.
4. **Compensation & benefits** (`ingest/heuristics_comp.py`): salary parsing (ranges/periods), bonus/benefits detection, workload/percentage inference.
5. **Coordinator** (`ingest/heuristics_runner.py`): orchestrate the above modules in sequence, expose a stable interface to the pipeline (`apply_heuristics(profile, text, *, logger=...)`) and maintain shared logging/telemetry helpers.

**Migration notes**
- Move shared regex constants into the relevant modules and re-export commonly used helpers from `ingest/heuristics/__init__.py` to avoid churn in pipeline imports.
- Add unit tests per module (e.g., contact pairing, skill deduping, remote-percentage inference) so future heuristics can be added without touching unrelated files.
