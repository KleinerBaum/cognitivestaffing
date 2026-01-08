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

Navigation is **linear Back/Next**. “Next” is **disabled** until required fields for the current step are filled.

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

The Company step now uses the shared `render_step_layout` helper to align with the Known/Missing/Tools structure (`wizard/step_layout.py`).

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
  - `styles/`, `images/` – styling and assets

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

## Repository map (where to change what)

### “I want to change the wizard flow / UX”
- Step order, step ownership, required fields:
  - `wizard_router.py`
  - `wizard_pages/` (step definitions / metadata)
- Sidebar stepper/progress:
  - `sidebar/`
- Shared step layout pattern (recommended):
  - `wizard/step_layout.py` *(Known/Missing tabs with optional tools expander)*
  - `wizard/step_scaffold.py` *(add if not present; centralize Known/Missing/Validate/Nav)*

### “I want to change which fields are required/critical”
- Required fields (UI gating):
  - Step definitions in `wizard_pages/` and/or step modules
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
