# AGENTS.md — Cognitive Staffing (Recruitment Need Analysis Wizard)

This file contains **agent-focused** instructions for working in this repository.
It complements `README.md` (human onboarding) and is intended for tools like **Codex**, Copilot coding agent, Cursor agents, etc.

> Priority rules: User instructions > closest AGENTS.md > other docs.
> If you add nested `AGENTS.md` files later, the one closest to the edited file should take precedence.

---

## Project context (what you are building)

Cognitive Staffing is a **multi-step Streamlit wizard** that:
- ingests job ads (PDF/DOCX/URL/pasted text),
- extracts a structured **NeedAnalysisProfile** (schema + Pydantic models),
- guides users through a **fixed 8-step wizard** to fill gaps,
- generates recruiter-ready outputs (job ad draft, interview guide, Boolean search, exports/artifacts).

The project is **bilingual (DE/EN)**. UI copy and follow-up logic must remain consistent across both languages.

---

## Non-negotiable invariants (do not break)

### 1) Wizard UX contract (step flow)
- The wizard has a **fixed 8-step order**:
  1) Onboarding / Job Ad  
  2) Company  
  3) Team & Structure  
  4) Role & Tasks  
  5) Skills & Requirements  
  6) Compensation / Benefits  
  7) Hiring Process  
  8) Summary (Final Review + Exports)

- Navigation is **linear Back/Next**.
- **“Next” must remain disabled** until required fields for the current step are satisfied.

### 2) Per-step UI layout pattern (mandatory)
Each step must follow the same top-down structure:
1. **Known** (what we already have; compact + readable; optionally editable)
2. **Missing** (ask only what’s missing for that step)
3. **Validate** (required/critical fields + gating)
4. **Nav** (Back/Next)

**AI assistants/tools must NOT compete with the Missing form**.
Place assistants/tools inside an expander or a dedicated “Tools” area (not inline with the main form).

Preferred implementation helpers:
- `wizard/step_layout.py` (`render_step_layout` / shared layout utilities)
- If present (or added later): `wizard/step_scaffold.py` for centralized patterns.

### 3) Data contract & key consistency (critical)
This repo has a canonical schema + model contract. **Keys are not “just strings”.**
If you introduce/rename a field, you must propagate it across:
- JSON schema: `schema/need_analysis.schema.json`
- Pydantic/data models: `schemas.py` and/or `models/`
- UI step(s): `wizard/`, `wizard_pages/`, `ui_views/`
- Follow-ups (if relevant): `questions/`, `question_logic.py`, `wizard/services/followups.py`
- Validation / required mappings: `wizard/metadata.py`, tests
- Exports/generators: `generators/`, `exports/`, `artifacts/`

**Do not leave “dangling keys”** (schema != UI != followups).  
When in doubt: search the repo for the key and update every usage.

### 4) Step ownership rules (keep missing prompts where inputs live)
Certain prefixes belong to specific steps to keep follow-ups and missing-field badges discoverable in the UI.
If you change routing/ownership, update both UI + follow-up mapping coherently.

---

## Repository map (where to change what)

### Entry & routing
- `app.py` — Streamlit entry and global layout
- `wizard_router.py` — wizard routing + navigation guards
- `wizard/navigation/` — navigation state machine and query/session sync

### Wizard UI
- `wizard/` — canonical wizard implementation
- `wizard_pages/` — step definitions/metadata (legacy layer / proxies may exist)
- `wizard_tools/` — tool panels/assistants used by the wizard
- `wizard_tools/experimental/` — opt-in stage graph tooling (**guarded by** `ENABLE_AGENT_GRAPH=1`)
- `wizard/step_registry.py` — canonical step definitions (ordering + renderers)
- `sidebar/`, `ui_views/`, `components/` — shared UI pieces
- `styles/`, `images/` — styling/assets (prefer CSS/theme tokens over inline styling)

### Data contract
- `schema/need_analysis.schema.json` — canonical schema
- `schemas.py`, `models/` — Pydantic/data models

### Missing info & follow-ups
- `critical_fields.json` — critical fields per step
- `question_logic.py` + `questions/` — follow-up questions & orchestration
- `role_field_map.json` — role-dependent field priorities
- `wizard/services/followups.py` — canonical follow-up generation (LLM + fallback)
- `wizard/missing_fields.py` — helpers for missing-field detection
- `wizard/step_status.py` — step-level status helpers

### LLM & pipelines
- `openai_utils/` — OpenAI client wrapper (Responses vs Chat, retries, fallbacks)
- `llm/` — prompt assembly, response schemas, JSON repair
- `llm/json_repair.py` — schema-guided retries/repair behavior
- `pipelines/` — ingest → extraction → repair → exports
- `ingest/`, `nlp/` — parsing + heuristics
- `prompts/` — prompt templates and prompt fragments

### Outputs
- `generators/` — job ads, interview guides, Boolean search, etc.
- `exports/` — export wiring and file generation
- `artifacts/` — generated files / caches

---

## Dev environment

### Requirements
- Python **>= 3.11**
- An OpenAI API key (for LLM-backed flows)
- (Optional but recommended) **Poetry**

### Install (recommended)
```bash
git clone https://github.com/KleinerBaum/cognitivestaffing.git
cd cognitivestaffing

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

poetry install
