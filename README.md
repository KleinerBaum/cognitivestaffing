# Cognitive Staffing (Recruitment Need Analysis Wizard)

A multi-step **Streamlit wizard** that turns unstructured job ads (PDF, DOCX, URLs, pasted text) into a structured **NeedAnalysisProfile** JSON plus recruiter-ready outputs (job ad draft, interview guide, Boolean search, etc.).

**Live app(s)**  
- Production / Primary: https://gerriserfolgstracker.streamlit.app/ *(your deployment; may redirect depending on Streamlit settings)*  
- Reference / Demo: https://cognitivestaffing.streamlit.app/

---

## Table of Contents
- [What it does](#what-it-does)
- [Wizard flow (UX contract)](#wizard-flow-ux-contract)
- [Architecture (high level)](#architecture-high-level)
- [Repository map (where to change what)](#repository-map-where-to-change-what)
- [Setup & run locally](#setup--run-locally)
- [LLM configuration](#llm-configuration)
- [Testing](#testing)
- [Common development tasks](#common-development-tasks)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

---

## What it does

1) **Ingest & parse** job ads (PDF/DOCX/URL/text).  
2) **Extract** structured data into a canonical NeedAnalysisProfile (schema + Pydantic models).  
3) **Guide the user** through an 8-step bilingual wizard to review + enrich missing information.  
4) **Generate outputs** (job ad, Boolean search, interview guide, summaries, exports).

The wizard supports German and English job ads and maps common DE/EN section headings (“Ihre Aufgaben / Your Tasks”, “Ihr Profil / Your Profile”, “Benefits / Wir bieten”, …) into the correct fields.

---

## Wizard flow (UX contract)

> This section is the **source of truth** for how steps must behave.
> If a step feels “unstructured”, it is violating this contract.

### The 8 steps (fixed order)

1. Onboarding / Job Ad
2. Business-Kontext
3. Team & Structure
4. Role & Tasks
5. Skills & Requirements
6. Compensation / Benefits
7. Hiring Process
8. Summary (Final Review + Exports)

The onboarding step starts with a single hero block (logo + eyebrow/headline/subheadline) plus a primary CTA and a compact three-step timeline, followed immediately by a two-panel URL vs. upload call-to-action with an explicit OR divider so the first screen is focused and uncluttered. The hero copy stays bilingual and directs users to the onboarding source anchor (`#onboarding-source`) to keep the value prop → action flow clear. The onboarding details expander reinforces the extraction process, privacy handling, and accuracy expectations in bilingual copy. Subsequent steps keep the layout focused on the form without any global hero/banner. Secondary messaging stays in helper text or expanders.

Navigation defaults to **linear Back/Next**, but steps can optionally resolve a dynamic next step for branching flows. “Next” is **disabled** until required fields for the current step are filled, with inline validation messaging below the controls.
The navigation footer also shows an emoji stepper that mirrors the localized step labels, highlighting active/done/upcoming states for quick context.
Validation errors always render in a reserved area below the navigation controls to avoid layout shifts and to keep bilingual messaging consistent across steps.
Field labels can include origin markers (🔎 extracted / 🤖 suggested / ✍️ manual) so reviewers can immediately see where a value came from.
Steps can be conditionally inactive based on the profile or schema (for example, the Team step may be skipped if the team data model is disabled); navigation and deep links must always land on the nearest active step.

The sidebar Flow mode toggle can switch between the guided multi-step flow and a single-page view that renders all steps in order inside expanders, with a top-level missing-fields summary to validate everything at once.

The Business-Kontext step captures the domain-first context (business domain, industry codes, and optional organisation details), while company contact and department inputs remain accessible so missing-field badges appear where inputs live.
Location follow-ups (`location.*`) are routed to the Business-Kontext step to ensure missing prompts surface alongside the location inputs.
Position team follow-ups (`position.team_*`) are routed to the Business-Kontext step to match where the team structure inputs are rendered.

The Summary step is organized into tabs for **Overview**, **Edit (core company/team/role/skills/compensation/process fields)**, **Exports**, and **Warnings** to keep review, export, and validation in one place. The Exports tab now includes a compact artifact list that centralizes downloads.

### Per-step UI pattern (mandatory)

Every step MUST render in the same top-down pattern:

1) **Known** (readable & optionally editable)  
   - Show what we already have (extraction + previous edits).
   - Keep it compact: summary cards, 2-column layout.

2) **Missing** (dynamic, user-friendly collection)  
   - Ask only what’s missing for THIS step.
   - Use short questions, helpful defaults, and inline explanations.
   - Optional: AI assistants/tools belong in a dedicated “Tools” area (see below).

3) **Validate** (required/critical fields)  
   - Clearly highlight missing required fields.
   - “Next” triggers validation and keeps the user on the step if required fields are missing.

4) **Next / Back navigation**  
   - One primary action: continue.

Missing prompts should not duplicate inputs that are already editable in the Known tab; inline fields (for example, the Team reporting line) are edited once to avoid conflicting updates.

The baseline UX uses the guided-flow UI kit in `app.py` (emoji stepper, context bar, progress microcopy, and inline saved feedback) to keep navigation stable without layout shifts.
Wizard widget keys should always be generated via `wiz.k(...)` so session state remains namespaced for multi-wizard and multi-repo safety.

The Business-Kontext step now uses the shared `render_step_layout` helper to align with the Known/Missing/Tools structure (`wizard/step_layout.py`).
The Team & Structure step now uses the shared `render_step_layout` helper to align with the Known/Missing/Tools structure (`wizard/step_layout.py`).

### Tools & assistants (UX rule)

AI tools / assistants must NEVER compete with the main “Missing” form.
They should be placed in an **expander** (e.g., “Assistants & Tools”) or a secondary side-panel.

---

## Architecture (high level)

The repo is organized so schema, domain logic, LLM integration, and UI are separated.

- Entry & routing  
  - `app.py` – Streamlit entry + global layout  
  - `wizard_router.py` – wizard routing + navigation guards  
  - `wizard/navigation/` – navigation state machine, UI controls, and session/query param sync

- Wizard UI  
  - `wizard/`, `wizard_pages/`, `wizard_tools/` – step UIs + wizard utilities (legacy `wizard_pages` proxies the step registry)  
  - `wizard_tools/experimental/` – opt-in stage graph tooling for agent workflows (`ENABLE_AGENT_GRAPH=1`)  
  - `ui/` – shared Streamlit wizard UX kit modules (including compatibility shims)  
  - `wizard/step_registry.py` – canonical step definitions (metadata + renderers + ordering)  
  - `docs/dev/wizard-steps.md` – developer guide for adding new steps safely  
  - `sidebar/`, `ui_views/`, `components/` – shared UI components  
  - `styles/`, `images/` – styling and assets (including onboarding hero CTA/timeline styles, sidebar hero/stepper theme CSS instead of inline `app.py`, `.onboarding-source-inputs` layout rules, and text-based previews for key UX elements such as steppers, origin markers, and validation areas)  
  - `docs/design-system.md` – theme tokens plus onboarding hero CTA/timeline, source input panels, and motion rules for dark/light UI

- Data contract  
  - `schema/need_analysis.schema.json` – canonical schema  
  - `schemas.py`, `models/` – Pydantic/data models

- Missing info & follow-up logic  
  - `critical_fields.json` – critical fields per step  
  - `question_logic.py` + `questions/` – follow-up questions & logic  
  - `role_field_map.json` – role-dependent field priorities
  - `wizard/services/followups.py` – canonical follow-up generation (LLM + fallback)
  - Follow-up responses are schema-validated with JSON repair heuristics, a schema-guided repair retry, and redacted logging before falling back to defaults.
  - `wizard/missing_fields.py` – pure helpers for missing-field detection
  - `wizard/services/` – canonical gap, validation, and job description services shared by UI and agent tools
  - `wizard/step_status.py` – step-level missing required/critical status helpers

- LLM & pipelines  
  - `openai_utils/` – OpenAI client wrapper (Responses vs Chat, retries, fallbacks)  
  - `llm/` – response schemas, prompt assembly  
  - `pipelines/` – ingest → extraction → repair → exports  
  - Structured extraction enforces JSON-only outputs, performs a schema-guided repair retry, and records low-confidence recovery metadata for the wizard flow.
  - ESCO lookups plus extraction/follow-up LLM results are cached per session (keyed by input hashes) to avoid re-running expensive steps on Streamlit reruns.
  - `ingest/`, `nlp/` – parsing + heuristics

- Outputs  
  - `generators/`, `exports/` – job ads, interview guides, Boolean search, etc.  
  - `artifacts/` – generated files / caches

---

## LLM configuration

- **Cost saver toggle (sidebar)**: when enabled, the wizard forces the lightweight model route and clamps `max_completion_tokens` to a tighter ceiling for cheaper, faster responses. Explicit model overrides still take priority if a caller sets one directly.
- **Quick vs. Precise mode**: Quick lowers reasoning effort and Precise raises it; both respect the cost saver toggle when it is enabled.
- **Responses fallbacks**: suggestion helpers only log chat fallback usage when the Responses client returns a structured `ResponsesCallResult` to avoid type mismatches during tests or mocking.

### Cost controls

Use these environment variables (or Streamlit secrets) to cap spend and steer model choices:

- **`OPENAI_SESSION_TOKEN_LIMIT` / `OPENAI_TOKEN_BUDGET`**: session-wide token budget guard. Once the limit is exceeded, OpenAI calls stop with a bilingual warning.
- **`REASONING_EFFORT`**: hint for reasoning depth (`none`/`minimal`/`low`/`medium`/`high`). Lower values reduce cost; higher values unlock more deliberative responses.
- **`MODEL_ROUTING__<task>` overrides**: per-task model routing overrides (task keys match `ModelTask` in `config/models.py`, e.g. `job_ad`, `interview_guide`, `profile_summary`, `salary_estimate`, `follow_up_questions`).

The sidebar includes a token usage summary with a per-request table (see `sidebar/__init__.py`) so you can review spend while running the wizard.

**Example `.env` (low-cost defaults):**

```bash
OPENAI_SESSION_TOKEN_LIMIT=12000
REASONING_EFFORT=minimal
MODEL_ROUTING__job_ad=gpt-4o-mini
MODEL_ROUTING__interview_guide=gpt-4o-mini
```

**Example `.streamlit/secrets.toml`:**

```toml
OPENAI_TOKEN_BUDGET = "12000"
REASONING_EFFORT = "minimal"
MODEL_ROUTING__job_ad = "gpt-4o-mini"
MODEL_ROUTING__interview_guide = "gpt-4o-mini"
```

---

## Repository map (where to change what)

### “I want to change the wizard flow / UX”
- Step order, step ownership, required fields:
  - `wizard_router.py`
  - `wizard/navigation/`
  - `wizard_pages/` (step definitions / metadata)
  - `docs/refactor/wizard-unification-audit.md` (maintainability audit + refactor plan)
- Sidebar stepper/progress:
  - `sidebar/`
  - Feature flag: set `st.session_state["feature.sidebar_stepper_v1"] = True` to preview the sidebar stepper.
  - Navigation flag: set `st.session_state["feature.sidebar_stepper_nav_v1"] = True` to allow clicking previous steps in the sidebar stepper.
  - Step-panel fade: set `WIZARD_STEP_FORM_FADE=1` (env/secrets) or `st.session_state["wizard.step_form_fade"] = True` to enable the optional step fade wrapper.
  - Form-based fade mode: toggle `USE_FORM_PANEL_FADE` in `app.py` to render wizard steps inside a `st.form` with submit-based navigation.
- Sidebar settings (language, theme, intro banner, advanced LLM options):
  - `sidebar/__init__.py`
- Shared step layout pattern (recommended):
  - `wizard/step_layout.py` *(Known/Missing tabs with optional tools expander)*
  - `wizard/step_scaffold.py` *(add if not present; centralize Known/Missing/Validate/Nav)*
  - `render_step_layout` accepts localized strings or `(de, en)` tuples for titles/intro copy.

### “I want to change which fields are required/critical”
- Required fields (UI gating):
  - Step definitions in `wizard_pages/` and/or step modules
  - Ensure `PAGE_FOLLOWUP_PREFIXES` + `validate_required_fields_by_page` stay aligned (`wizard/metadata.py`, `tests/test_required_fields_mapping.py`)
- Critical fields (follow-up prompts + missing badges):
  - `critical_fields.json`
  - `question_logic.py` / `questions/`

### “I want to add a new field to the profile”
1) Update schema:
   - `schema/need_analysis.schema.json`
2) Update Pydantic/models:
   - `schemas.py` and/or `models/`
3) Ensure normalization defaults:
   - `core/` and/or `utils/`
4) Add it to the correct step:
   - `wizard_pages/<step>.py` + step UI in `wizard_pages/` or `wizard/`
5) Add follow-up question (optional):
   - `questions/` + `question_logic.py`

### “I want to adjust LLM behavior / models”
- Model routing + capabilities:
  - `config/models.py`
- Prompts:
  - `prompts/`
- Client behavior (Responses/Chat, retries, fallbacks):
  - `openai_utils/`
  - `ALLOW_LEGACY_FALLBACKS=0` disables legacy Chat Completions fallbacks, leaving static benefit shortlists as the last-resort suggestion source.
- JSON repair and schema-guided fallback retries:
  - `llm/json_repair.py`

### “I want to add a new export / generator”
- Implement generator:
  - `generators/`
- Wire into export UI:
  - Summary step (final review) in `wizard_pages/` / `ui_views/`
- Write artifact handling:
  - `exports/` and/or `artifacts/`

---

## Setup & run locally

### Requirements
- Python ≥ 3.11
- OpenAI API key
- (Optional) Poetry

### Install (recommended with Poetry)
```bash
git clone https://github.com/KleinerBaum/cognitivestaffing.git
cd cognitivestaffing

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

poetry install
```

---

## Testing

```bash
poetry run pytest
```

Streamlit AppTest regression checks (including the ESCO selector state guard) run in the same
`pytest` suite and do not require network access.

Some wizard tests stub Streamlit containers/columns, so stubs should mimic context-manager
behavior and three-column layouts.

The test suite also validates that rule-based extraction fields stay aligned with the canonical
NeedAnalysis schema, so rule path drift fails fast in CI.

Job ad fixtures live under `tests/fixtures/job_ads/`. Use the helper in
`tests/fixtures/job_ads/__init__.py` to load UTF-8 fixture text for regression
tests.

---

## Troubleshooting

- Optional flow helpers (for example, company autofill suggestions) may be unavailable in slim flow
  variants; missing optional dependencies are expected and only logged at debug level.
- To enable the wizard flow diagram for debugging, set `DEBUG_FLOW_DIAGRAM=true` in the environment
  (or Streamlit secrets) and refresh the app. The Mermaid output appears under the
  “Debug: Flow diagram” expander in the wizard UI for easy copy/paste.
- If you encounter “missing ScriptRunContext” warnings, ensure background tasks only compute data
  and keep Streamlit UI/session-state updates on the main thread.
- Recoverable wizard failures now surface a retry button and a UI-only reset option; prefer UI
  resets before clearing the full profile to avoid losing captured data.
- ESCO occupation selector state is split between widget and profile keys to avoid Streamlit
  session-state mutation errors; keep widget changes on `ui.position.esco_occupation_widget`.
- Avoid committing binary screenshots in PRs; add any required images manually after review to
  keep diffs lightweight.
