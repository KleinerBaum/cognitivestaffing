# AGENTS.md — Cognitive Staffing (Recruitment Need Analysis Wizard)

This file contains agent-focused instructions for working in this repository. It complements `README.md` and is intended for coding agents such as Codex, Copilot coding agent, Cursor agents, and similar tools.

> Priority order: user instructions > closest `AGENTS.md` > other repository docs.  
> If nested `AGENTS.md` files are added later, the file closest to the edited code wins.

---

## 1) Project context

Cognitive Staffing is a multi-step Streamlit wizard that:

- ingests job ads (`PDF`, `DOCX`, URL, pasted text),
- extracts a structured `NeedAnalysisProfile` (`JSON Schema` + `Pydantic` models),
- guides users through a fixed **8-step wizard** to fill gaps,
- generates recruiter-ready outputs (job ad draft, interview guide, Boolean search, exports/artifacts).

The project is bilingual (`DE` / `EN`).  
UI copy, validation copy, follow-up logic, and generated outputs must remain internally consistent across both languages.

---

## 2) Current OpenAI integration policy (critical)

This repository is being optimized for a **strict GPT-5-nano-only runtime** for all **non-embedding** generation tasks.

### Non-negotiable OpenAI rules

1. **Use the Responses API as the primary integration path.**
   - Do not introduce new Chat Completions-only flows unless there is a documented technical blocker.
   - If an older Chat path remains temporarily, it must remain compatible with the same model-routing policy and be treated as legacy.

2. **Do not silently upgrade model families.**
   - Do not “helpfully” switch tasks to `gpt-5.4`, `gpt-5-mini`, `gpt-4o-mini`, `o3`, `o4-mini`, etc.
   - If the repo is in strict nano mode, all non-embedding tasks must resolve to `gpt-5-nano`.

3. **Reasoning defaults for GPT-5 nano**
   - Treat `reasoning.effort="minimal"` as the low-latency baseline for GPT-5 nano work.
   - Raise to `low` only when evals or regression tests show a real quality gain.
   - Do **not** assume `reasoning.effort="none"` is supported for `gpt-5-nano`.
   - Do not change model family to compensate for prompt or schema problems.

4. **Keep outputs compact.**
   - Default to low/compact verbosity.
   - Prefer explicit output contracts over long natural-language prompts.
   - For structured tasks, require exact shape and avoid extra prose.

5. **Use stateful Responses patterns correctly.**
   - In multi-turn or tool flows, prefer `previous_response_id` instead of replaying large histories.
   - Re-send current developer/system instructions each turn as needed; do not assume previous instructions are automatically preserved.

6. **Use structured outputs correctly.**
   - In the Responses API, structured output belongs under `text.format`, not legacy `response_format`.
   - If the model is calling application functions, prefer **function calling** with a strict schema.
   - Use strict schemas unless there is a documented reason not to.

7. **Tooling must match GPT-5 nano capabilities.**
   - Allowed in principle for `gpt-5-nano`: function calling, structured outputs, web search, file search, image generation, code interpreter, MCP.
   - Not supported for `gpt-5-nano`: tool search, computer use, hosted shell, apply patch, skills.
   - Never request unsupported tool types from a nano-only runtime.
   - Add or preserve explicit capability guards in routing / payload assembly.

8. **One change at a time.**

9. **Tools default and guards.**
   - `RESPONSES_ALLOW_TOOLS` may remain enabled by default when guardrails are active.
   - Explicitly reject unsupported GPT-5-nano tool types (`tool_search`, `computer_use`, `hosted_shell`, `apply_patch`, `skills`).
   - Keep tool-enabled flows Responses-first and schema-constrained.

10. **Troubleshooting reminders.**
   - If a non-nano model appears, verify `STRICT_NANO_ONLY=true`, effective env/secrets values, and task-routing overrides.
   - For structured output failures in Responses mode, validate payload shape under `text.format` first before touching model routing.
   - Keep timeout/retry behavior explicit and avoid silent endpoint drift.

   - When migrating prompts or payloads, change one variable at a time:
     - model routing,
     - reasoning effort,
     - verbosity,
     - tool policy,
     - output schema / prompt contract.
   - Run verification after each meaningful change.

---

## 3) Non-negotiable product invariants (do not break)

### 3.1 Wizard UX contract

The wizard has a fixed 8-step order:

1. Onboarding / Job Ad
2. Company
3. Team & Structure
4. Role & Tasks
5. Skills & Requirements
6. Compensation / Benefits
7. Hiring Process
8. Summary (Final Review + Exports)

Rules:

- Navigation is linear: **Back / Next**
- `Next` must remain disabled until required fields for the current step are satisfied
- Do not skip, merge, reorder, or dynamically hide canonical steps without an explicit repo-wide migration

### 3.2 Per-step layout pattern (mandatory)

Each step must follow the same top-down structure:

1. **Known** — what is already known; compact, readable, optionally editable
2. **Missing** — ask only what is missing for that step
3. **Validate** — required/critical fields + gating
4. **Nav** — Back / Next

AI assistants and tools must **not** compete with the Missing form.

- Put assistants/tools inside an expander or dedicated **Tools** area
- Do not place assistant controls inline with required form fields
- Do not bury required field gating behind optional AI actions

Preferred helpers:

- `wizard/step_layout.py`
- `wizard/step_scaffold.py` if present
- centralized layout helpers over ad-hoc per-step variants

### 3.3 Data contract and key consistency (critical)

This repo has a canonical schema/model/UI contract.  
Keys are not “just strings”.

If you add, remove, rename, or re-route a field, you must propagate the change across all affected layers:

- JSON Schema: `schema/need_analysis.schema.json`
- Pydantic / data models: `schemas.py`, `models/`
- Wizard UI: `wizard/`, `wizard_pages/`, `ui_views/`
- Follow-ups: `questions/`, `question_logic.py`, `wizard/services/followups.py`
- Validation / gating metadata: `wizard/metadata.py`, `critical_fields.json`, tests
- Outputs / generators / exports: `generators/`, `exports/`, `artifacts/`

Do not leave dangling keys where `schema != model != UI != followups != generators`.

When in doubt:

- grep the repo for the key,
- update every usage,
- update tests,
- verify DE and EN copy.

### 3.4 Step ownership rules

Certain field prefixes belong to specific steps so that:

- missing prompts appear where users expect them,
- badges and counters remain discoverable,
- follow-up ownership remains stable,
- gating remains interpretable.

If you change field ownership or routing:

- update UI placement,
- update step metadata,
- update follow-up mapping,
- update missing-field detection,
- update tests.

Do not move ownership in only one layer.

---

## 4) Repository map

### Entry and routing

- `app.py` — Streamlit entry and global layout
- `wizard_router.py` — wizard routing and navigation guards
- `wizard/navigation/` — navigation state, query/session sync

### Wizard UI

- `wizard/` — canonical wizard implementation
- `wizard_pages/` — step definitions / metadata (legacy proxy layer may remain)
- `wizard_tools/` — tool panels and assistants used by the wizard
- `wizard_tools/experimental/` — opt-in graph tooling, guarded by `ENABLE_AGENT_GRAPH=1`
- `wizard/step_registry.py` — canonical step definitions
- `sidebar/`, `ui_views/`, `components/`, `ui/` — shared UI pieces
- `styles/`, `images/` — styling and assets

### Data contract

- `schema/need_analysis.schema.json` — canonical schema
- `schemas.py`, `models/` — typed data models

### Missing information and follow-ups

- `critical_fields.json` — critical fields per step
- `question_logic.py`, `questions/` — follow-up orchestration
- `role_field_map.json` — role-dependent field priorities
- `wizard/services/followups.py` — canonical follow-up generation
- `wizard/missing_fields.py` — missing-field helpers
- `wizard/step_status.py` — step-level status helpers

### LLM, OpenAI, and pipelines

- `openai_utils/` — OpenAI client wrapper, payload assembly, retries, legacy fallbacks
- `llm/` — prompt assembly, response schemas, JSON repair, routing helpers
- `llm/json_repair.py` — schema-guided retries / repair
- `pipelines/` — ingest → extraction → repair → outputs
- `ingest/`, `nlp/` — parsing and heuristics
- `prompts/` — prompt templates and fragments
- `config/` — runtime config and model-routing settings

### Outputs

- `generators/` — job ads, interview guides, Boolean search, summaries, etc.
- `exports/` — export wiring and file generation
- `artifacts/` — generated files / caches

### Testing and quality

- `tests/`
- `pyproject.toml`
- `pytest.ini`

---

## 5) Working rules for coding agents

### 5.1 Before editing

Always inspect the closest relevant files first. For model/runtime changes, start with:

- `config/`
- `openai_utils/`
- `llm/`
- `prompts/`
- `generators/`
- `wizard/services/followups.py`

For schema/field changes, start with:

- `schema/need_analysis.schema.json`
- `schemas.py`
- `wizard/metadata.py`
- `critical_fields.json`
- `question_logic.py`
- affected wizard step files
- generators / exports / tests

### 5.2 Change discipline

Make small, reviewable, cohesive changes.

Do:

- preserve existing interfaces unless you update all callers,
- keep UI / schema / follow-up / export layers in sync,
- reuse canonical constants and enums,
- prefer centralized helpers over copy-pasted branch logic,
- document assumptions in the final report.

Do not:

- mix unrelated refactors into the same change,
- rewrite prompts and routing everywhere without tests,
- add alternate model families “just in case”,
- leave dead fallback logic behind.

### 5.3 Prompting rules for this repo

Because this app is nano-optimized:

- keep prompts short, explicit, and contract-driven,
- specify exact section order or JSON/Markdown shape,
- forbid extra explanatory text around structured outputs,
- add lightweight completeness/verification instructions before raising reasoning effort,
- prefer prompt fixes over model escalation.

For tool-enabled prompts:

- keep tool instructions unambiguous,
- define stop conditions,
- define when zero tool calls is acceptable,
- constrain callable tools where possible.

### 5.4 Function calling and structured outputs

When adding or editing OpenAI payloads:

- prefer strict function schemas,
- set `additionalProperties: false` where appropriate,
- keep function names stable and descriptive,
- use `tool_choice` / allowed-tool constraints when needed,
- use `parallel_tool_calls=false` unless parallelism is explicitly safe and beneficial,
- use `text.format` for structured model responses in the Responses API.

### 5.5 Stateful Responses usage

When handling multi-turn flows:

- prefer `previous_response_id` for chained reasoning/tool workflows,
- avoid replaying large assistant histories manually unless necessary,
- re-send current instructions if they still matter,
- keep retries schema-aware and deterministic.

---

## 6) Debugging and verification rules

### 6.1 Required reporting for fixes and migrations

When making a meaningful change, report:

- the problem being fixed,
- repro steps,
- expected behavior,
- actual behavior,
- files changed,
- verification commands run,
- residual risk or known tradeoffs.

Do not summarize away important errors.  
Include full stack traces or failing command output when relevant.

### 6.2 Quality gates

Use the project’s configured tooling where available.

Typical commands:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
poetry install --with dev
pytest -q
ruff check .
mypy .
streamlit run app.py

If a command is not available in the environment, say so explicitly.

6.3 Model-routing verification

For any model migration or routing change, verify all of the following:

quick mode resolves to the intended model/runtime policy,

precise mode resolves to the intended model/runtime policy,

no hidden fallback upgrades remain,

extraction still works,

follow-up generation still works,

job ad generation still works,

interview guide generation still works,

exports still work,

structured-output parsing still works,

tool-enabled flows do not request unsupported nano tools.

Recommended grep pass for model migrations:

grep -Rni "gpt-4" .
grep -Rni "gpt-5-mini" .
grep -Rni "gpt-5.1" .
grep -Rni "o3" .
grep -Rni "o4" .
grep -Rni "OPENAI_MODEL" .
grep -Rni "DEFAULT_MODEL" .
grep -Rni "LIGHTWEIGHT_MODEL" .
grep -Rni "MEDIUM_REASONING_MODEL" .
grep -Rni "HIGH_REASONING_MODEL" .
grep -Rni "MODEL_ROUTING" .
grep -Rni "previous_response_id" .
grep -Rni "reasoning" .
grep -Rni "verbosity" .
7) Security and privacy rules

Never hardcode API keys or secrets

Never print secrets in logs

Redact sensitive user/job-ad/company data in debug output where possible

Use least-privilege external scopes for Google integrations

Do not expand data retention casually

Treat uploaded documents and extracted profile data as sensitive business data

For OpenAI requests:

prefer stable, explicit schemas,

minimize unnecessary prompt bloat,

avoid shipping raw internal debug context to the model unless needed.

8) Bilingual consistency rules

Whenever a change affects:

labels,

help text,

validation text,

follow-up phrasing,

generated section titles,

warning or empty states,

verify both DE and EN.

Do not update only one language path unless the feature is intentionally language-specific and documented as such.

9) Definition of done

A change is done only when all of the following are true:

The edited feature works in the Streamlit app

The wizard step contract is preserved

The schema/model/UI/follow-up/export layers are aligned

DE/EN behavior remains coherent

Tests or targeted manual verification are run

No unsupported GPT-5-nano tool path was introduced

No silent model-family fallback remains for nano-only flows

The final report clearly states what changed and how it was verified

10) Dev environment
Requirements

Python >=3.11

OpenAI API key

Poetry recommended
