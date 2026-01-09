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
2. Company
3. Team & Structure
4. Role & Tasks
5. Skills & Requirements
6. Compensation / Benefits
7. Hiring Process
8. Summary (Final Review + Exports)

The onboarding step starts with a single hero block (logo + headline/subheadline) plus a primary CTA and a compact three-step timeline, followed immediately by a two-panel URL vs. upload call-to-action with an explicit OR divider so the first screen is focused and uncluttered. Subsequent steps keep the layout focused on the form without any global hero/banner. Secondary messaging stays in helper text or expanders to keep the value prop → action flow clear.

Navigation is **linear Back/Next**. “Next” is **disabled** until required fields for the current step are filled.

The Company step owns company profile, contact, and department details (`department.*`) so department follow-ups and missing-field badges appear where the inputs live.
Location follow-ups (`location.*`) are also routed to the Company step to ensure missing prompts surface alongside the location inputs.
Position team follow-ups (`position.team_*`) are routed to the Company step to match where the team structure inputs are rendered.

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
   - “Next” stays disabled until validation passes.

4) **Next / Back navigation**  
   - One primary action: continue.

Missing prompts should not duplicate inputs that are already editable in the Known tab; inline fields (for example, the Team reporting line) are edited once to avoid conflicting updates.

The Company step now uses the shared `render_step_layout` helper to align with the Known/Missing/Tools structure (`wizard/step_layout.py`).
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

- Wizard UI  
  - `wizard/`, `wizard_pages/`, `wizard_tools/` – step UIs + wizard utilities  
  - `wizard/step_registry.py` – canonical step order metadata  
  - `sidebar/`, `ui_views/`, `components/` – shared UI components  
  - `styles/`, `images/` – styling and assets (including sidebar hero/stepper and `.onboarding-source-inputs` layout rules)  
  - `docs/design-system.md` – theme tokens plus onboarding hero CTA/timeline, source input panels, and motion rules for dark/light UI

- Data contract  
  - `schema/need_analysis.schema.json` – canonical schema  
  - `schemas.py`, `models/` – Pydantic/data models

- Missing info & follow-up logic  
  - `critical_fields.json` – critical fields per step  
  - `question_logic.py` + `questions/` – follow-up questions & logic  
  - `role_field_map.json` – role-dependent field priorities
  - `wizard/missing_fields.py` – pure helpers for missing-field detection
  - `wizard/step_status.py` – step-level missing required/critical status helpers

- LLM & pipelines  
  - `openai_utils/` – OpenAI client wrapper (Responses vs Chat, retries, fallbacks)  
  - `llm/` – response schemas, prompt assembly  
  - `pipelines/` – ingest → extraction → repair → exports  
  - `ingest/`, `nlp/` – parsing + heuristics

- Outputs  
  - `generators/`, `exports/` – job ads, interview guides, Boolean search, etc.  
  - `artifacts/` – generated files / caches

---

## LLM configuration

- **Cost saver toggle (sidebar)**: when enabled, the wizard forces the lightweight model route and clamps `max_completion_tokens` to a tighter ceiling for cheaper, faster responses. Explicit model overrides still take priority if a caller sets one directly.
- **Quick vs. Precise mode**: Quick lowers reasoning effort and Precise raises it; both respect the cost saver toggle when it is enabled.

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
  - `wizard_pages/` (step definitions / metadata)
- Sidebar stepper/progress:
  - `sidebar/`
  - Feature flag: set `st.session_state["feature.sidebar_stepper_v1"] = True` to preview the sidebar stepper.
  - Navigation flag: set `st.session_state["feature.sidebar_stepper_nav_v1"] = True` to allow clicking previous steps in the sidebar stepper.
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
