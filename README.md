# Cognitive Staffing

Cognitive Staffing is a multi-step Streamlit wizard that turns unstructured job ads (PDF, DOCX, URLs, or pasted text) into a structured **NeedAnalysisProfile** JSON and recruiter‑ready outputs (job ad, interview guide, Boolean search, etc.). It combines rule‑based ingest with OpenAI’s Responses API and reasoning models to prefill company, role, team, process, and compensation details, then guides users through eight bilingual steps to review, enrich, and export the results.

Live app: https://cognitivestaffing.streamlit.app/

---

## Key features

- **Eight-step bilingual wizard**  
  Onboarding → Company → Team & Structure → Role & Tasks → Skills & Requirements → Compensation → Hiring Process → Summary. Each step includes EN/DE intros, validations, and inline helper texts.

- **Required field & missing‑info guardrails**  
  Required fields are clearly marked; the *Next* button shows bilingual warnings listing missing required fields and blocks navigation until they are filled. Critical fields per step drive focused follow‑up questions and ChatKit prompts stored in `critical_fields.json`.

- **AI extraction & NeedAnalysisProfile normalization**
  Ingest heuristics plus OpenAI’s Responses API map job ads into the `NeedAnalysisProfile` schema (backed by `schema/need_analysis.schema.json` and Pydantic models). Extraction separates responsibilities vs. requirements, maps benefits, hiring process, and company info, and applies schema‑safe defaults so downstream views never crash on missing data.
- **Missing-section repair prompts**
  When structured extraction leaves gaps, a dedicated bilingual prompt retries only the missing fields so follow-up questions and exports stay aligned to the schema instead of falling back to plain error text.

- **ChatKit assistants for interactive enrichment**  
  Multiple embedded assistants help refine the profile:
  - **Follow-Up Q&A assistant** – asks short, targeted questions for missing critical fields on each step and writes answers into the profile.
  - **Company insights assistant** – enriches `company.*` fields (industry, size, HQ, website, description) using light public hints and user Q&A.
  - **Team composition advisor** – suggests typical team sizes, reporting lines, and org context for the role.
  - **Role responsibilities brainstormer** – proposes role‑specific responsibilities, with accept/reject per bullet.
  - **Skill-set expander** – suggests related skills/certifications and classifies them as required vs. nice‑to‑have.
  - **Compensation range assistant** – proposes salary ranges and helps fill `compensation.salary_min/max` and benefits.
  - **Hiring process planner** – drafts stage sequences and writes them into `process.hiring_process`.

- **Multilingual section detection & mapping**  
  German and English headings like *“Ihre Aufgaben / Your Tasks”*, *“Ihr Profil / Your Profile”*, *“Benefits / Unser Angebot / Wir bieten”* are recognized so responsibilities, requirements, benefits, and process sections land in the correct fields.

- **Structured skill buckets & ESCO integration**  
  Requirements are split into hard skills, soft skills, tools & technologies, languages, and certifications using heuristics plus optional ESCO lookups and cached reference data (`salary_benchmarks.json`, `skill_market_insights.json`).

- **OpenAI model routing (Quick vs. Precise)**  
  - **Quick / Schnell mode:** routes to a lightweight model tier (e.g. `gpt-4.1-mini`) with minimal reasoning for fast, cheap iterations.  
  - **Precise / Genau mode:** routes to reasoning‑tier models (e.g. `o4-mini`, optionally `o3`) with configurable `REASONING_EFFORT` for complex extraction, repair, and normalization flows.  
  Cache keys are mode‑aware so switching modes correctly refreshes AI outputs.

- **Responses API first, Chat Completions fallback**  
  Structured calls use the OpenAI Responses API with JSON schemas and retries. If streaming fails, returns empty content, or violates `response_format`, the client falls back to Chat Completions and, if needed, to static curated suggestions.

- **Boolean search & exports**  
  From the stored profile you can:
  - generate Boolean search strings,
  - assemble exportable job ads,
  - build interview guides and question sets.  
  Summary tabs separate Role & search, Job ad, and Interview guide for quick review.

- **AI transparency & auditability**
  The Summary view visually distinguishes AI‑suggested values (for example via italics and labels like “AI-suggested”) so recruiters know what to double‑check before exporting. Internally, the profile tracks which fields were touched by AI, enabling future audit trails and confidence indicators.
- **Resilient autofill controls**
  Accept/reject decisions for AI autofill suggestions are tracked across steps, and the Company step now binds its dependencies defensively so autofill UI remains available even when optional helpers are missing.

---

## Architecture overview

The repository is organized so that **schema**, **domain logic**, **LLM integration**, and **UI** are clearly separated:

- **Entry & configuration**
  - `app.py` – Streamlit entrypoint and global layout.
  - `config.py`, `config_loader.py` – environment variables, feature flags (Responses vs. Chat, ChatKit on/off, model overrides).
  - `schemas.py` – Pydantic models mirroring `NeedAnalysisProfile` and related objects.
  - `wizard_router.py` – step routing, navigation guards, step IDs.
  - `i18n.py` – bilingual texts and helper utilities.
  - `question_logic.py`, `critical_fields.json` – follow‑up question and critical‑field definitions.

- **Core domain & schema**
  - `core/` – domain models and helpers around `NeedAnalysisProfile`, schema registry, and validation.
  - `schema/need_analysis.schema.json` – canonical JSON Schema for profiles.
  - `models/` – data models and typed DTOs used across pipelines and UI.
  - `utils/` – normalization/repair helpers, salary/skill insights, ESCO lookups, JSON repair.

- **LLM & agents integration**
  - `openai_utils/` – OpenAI client wrapper (Responses vs. Chat, streaming, retries, fallbacks, vector store integration).
  - `llm/` – response schemas, prompt assembly, and LLM‑specific utilities.
  - `pipelines/` – end‑to‑end flows (ingest → extraction → repair → exports).
  - `integrations/` – external services like OpenAI Vector Store, company info, etc.
  - `generators/` – generators for job ads, interview guides, Boolean searches and other exports.
  - `infra/` – ChatKit / Agents server integration and other infra helpers.
  - `agent_setup.py` – registration of ChatKit workflows and assistant payloads.

- **NLP & ingest**
  - `ingest/` – PDF/DOCX parsing, URL and raw text ingest; section splitting.
  - `nlp/` – heading detection and heuristics for DE/EN section mapping.

- **UI & wizard flow**
  - `wizard/`, `wizard_pages/`, `wizard_tools/` – per‑step Streamlit UIs and wizard logic.
  - `sidebar/`, `ui_views/`, `components/` – shared UI components (tabs, summary, ChatKit panels).
  - `styles/`, `images/` – styling and static assets.

- **State & helpers**
  - `state/` – `st.session_state` helpers, profile persistence, mode toggles.
  - `constants/` – step IDs, enum constants, keys.
  - `typing_shims/` – compatibility shims.

- **Reference data**
  - `salary_benchmarks.json`, `skill_market_insights.json`, ESCO caches, benefits & compensation insights.

- **Tests & tooling**
  - `tests/`, `pytest.ini` – unit and integration tests.
  - `.devcontainer/`, `.github/workflows/`, `.tooling/` – CI, linting, dev environment.

---

## Installation

### Requirements

- Python ≥ 3.11
- OpenAI API key
- (Optional) ChatKit domain key and workflow IDs
- (Optional) Poetry for dependency management

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/KleinerBaum/cognitivestaffing.git
cd cognitivestaffing

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

```

### Reset API mode and model overrides

- **English:** If the app falls back to older models because of environment overrides, clear the flags in your `.env` or Streamlit secrets. Run `python -m cli.reset_api_flags` to strip `USE_CLASSIC_API`, `USE_RESPONSES_API`, and model tier overrides (`OPENAI_MODEL`, `DEFAULT_MODEL`, `LIGHTWEIGHT_MODEL`, `MEDIUM_REASONING_MODEL`, `REASONING_MODEL`, `OPENAI_BASE_URL`, `OPENAI_API_BASE_URL`). Add `-k EXTRA_KEY` to remove additional keys.
- **Deutsch:** Falls die App wegen gesetzter Umgebungsvariablen auf alte Modelle zurückfällt, entferne die Flags aus deiner `.env` oder den Streamlit-Secrets. Nutze `python -m cli.reset_api_flags`, um `USE_CLASSIC_API`, `USE_RESPONSES_API` sowie Modell-Overrides (`OPENAI_MODEL`, `DEFAULT_MODEL`, `LIGHTWEIGHT_MODEL`, `MEDIUM_REASONING_MODEL`, `REASONING_MODEL`, `OPENAI_BASE_URL`, `OPENAI_API_BASE_URL`) zu löschen. Mit `-k EXTRA_KEY` entfernst du weitere Schlüssel.
