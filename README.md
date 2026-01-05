# Cognitive Staffing

Cognitive Staffing is a multi-step Streamlit wizard that turns unstructured job ads (PDF, DOCX, URLs, or pasted text) into a structured **NeedAnalysisProfile** JSON and recruiter‑ready outputs (job ad, interview guide, Boolean search, etc.). It combines rule‑based ingest with OpenAI’s Chat Completions API and GPT‑5 reasoning models to prefill company, role, team, process, and compensation details, then guides users through eight bilingual steps to review, enrich, and export the results.

Live app: https://cognitivestaffing.streamlit.app/

---

## Key features

- **Eight-step bilingual wizard**
  Onboarding → Company → Team & Structure → Role & Tasks → Skills & Requirements → Compensation → Hiring Process → Summary. Each step includes EN/DE intros, validations, and inline helper texts.

- **Responsive layout for mobile & tablets**
  Wizard columns reflow to one or two per row on narrow screens, navigation buttons are mirrored at the top and bottom of each step, and wide tables/text areas stay usable via horizontal-safe containers so the flow remains scroll- and tap-friendly.

  - **Required field & missing‑info guardrails**
    Required fields are clearly marked; the *Next* button shows bilingual warnings listing missing required fields and blocks navigation until they are filled. Step headers now surface ⚠️ badges and a bilingual summary panel when critical fields are missing, and inline labels gain warning indicators/tooltips so users see what needs attention immediately. Critical fields per step drive focused follow‑up questions and ChatKit prompts stored in `critical_fields.json`. Step validation now aligns field ownership with the correct sections so later-stage items (e.g., seniority, compensation ranges, remote percentage, interview stages) only gate the step where they belong.
    Layout for these badges now uses fixed numeric column ratios so Streamlit renders consistently without type errors on missing-field sections.
    Auto-repair notices now sit in a collapsed bottom drawer so the main form stays uncluttered while the warning remains visible across the step.

  - **Linear Back/Next flow**
    Navigation strictly follows the eight-step order (Job Ad → Company → Team → Role Tasks → Skills → Benefits → Interview → Summary), ignores unknown step keys in query params, and keeps *Next* disabled on required fields instead of forcing users to hop back-and-forth.

- **AI extraction & NeedAnalysisProfile normalization**
  Ingest heuristics plus OpenAI’s Chat Completions API map job ads into the `NeedAnalysisProfile` schema (backed by `schema/need_analysis.schema.json` and Pydantic models). Extraction separates responsibilities vs. requirements, maps benefits, hiring process, and company info, and applies schema‑safe defaults so downstream views never crash on missing data. Canonical schema keys (for example, `company.name`, `position.job_title`, and `requirements.skill_mappings.*`) are enforced so legacy payloads are normalized instead of triggering JSON repairs.
  Malformed JSON responses are repaired with lightweight heuristics and a single schema-guided repair attempt before the UI falls back to defaults; when a fallback is used the profile marks `meta.extraction_fallback_active` so the wizard can warn the user. The Company step now surfaces a bilingual banner (“Wir konnten … nicht automatisch auslesen / We had trouble parsing…”) so users know to double-check the prefilled values.
- **Missing-section repair prompts**
  When structured extraction leaves gaps, a dedicated bilingual prompt retries only the missing fields so follow-up questions and exports stay aligned to the schema instead of falling back to plain error text.

  - **ChatKit assistants for interactive enrichment**
    Multiple embedded assistants help refine the profile:
    - **Follow-Up Q&A assistant** – asks short, targeted questions for missing critical fields on each step and writes answers into the profile.
    - **Company insights assistant** – enriches `company.*` fields (industry, size, HQ, website, description) using light public hints and user Q&A.
    - **Team composition advisor** – suggests typical team sizes, reporting lines, and org context for the role. When the assistant is unavailable (for example, rate limits), the wizard now shows a bilingual notice and still lets you continue to the next step. The advisor now remains disabled until a job title and reporting line are provided so downstream prompts never run with empty context.
    - **Role responsibilities brainstormer** – proposes role‑specific responsibilities, with accept/reject per bullet.
    - **Skill-set expander** – suggests related skills/certifications and classifies them as required vs. nice‑to‑have.
    - **Compensation range assistant** – proposes salary ranges and helps fill `compensation.salary_min/max` and benefits.
    - **Hiring process planner** – drafts stage sequences and writes them into `process.hiring_process`.

- **Multilingual section detection & mapping**
  German and English headings like *“Ihre Aufgaben / Your Tasks”*, *“Ihr Profil / Your Profile”*, *“Benefits / Unser Angebot / Wir bieten”*, *“Bewerbungsprozess / Interview Process”* are recognized and mapped so responsibilities, requirements, benefits, and process sections land in the correct fields. Benefits and hiring process bullets now reliably flow into `compensation.benefits` and `process.hiring_process` for DE/EN ads.

- **Structured skill buckets & ESCO integration**  
  Requirements are split into hard skills, soft skills, tools & technologies, languages, and certifications using heuristics plus optional ESCO lookups and cached reference data (`salary_benchmarks.json`, `skill_market_insights.json`).

- **OpenAI model routing (automatic, fixed defaults)**
  Lightweight classification or short-form Q&A calls default to `gpt-4o-mini`, while richer drafting flows (job ads, interview guides, summaries) use `gpt-4o` and escalate to `o3-mini` only for precise/high-effort runs. The routing layer now falls back through `gpt-4o` and `gpt-3.5-turbo` before touching GPT-5.2 tiers so everyday tasks stay inexpensive. Users no longer choose between Quick/Precise modes or base-model dropdowns; routing happens behind the scenes to keep performance and cost predictable. Default assistant outputs cap at 1,024 tokens to reduce cost; long-form generators (job ads, guides) continue to request higher limits where needed to avoid truncation.

- **Single-source task capabilities**
  Every AI task (structured extraction, follow-up drafting, JSON repair, salary estimation, and more) now pulls its preferred model and JSON/text capability flags from a unified `MODEL_CONFIG` map in `config/models.py`, reducing repeated fallbacks and making routing behaviour predictable in logs.

- **Responses API with strict JSON schema enforcement**
  Structured calls now use the OpenAI Responses API with JSON schemas (and strict mode where supported), falling back to Chat Completions only when models or payloads require it. Invalid JSON responses are repaired automatically (or retried on the chat client when needed) without asking users to toggle strictness, reducing noisy logs and latency. The upgraded SDK verifies compatibility with `gpt-5.2` and its mini/nano variants so new models stay available to the routing layer.

- **Responsive loading and timeout handling**
  LLM-triggered actions render Streamlit spinners (“Analysiere die Stellenbeschreibung… / Analyzing your job description…”) so users know work is in progress. Friendly bilingual timeout notices (“⏳ … länger als erwartet / taking longer than usual…”) surface when OpenAI calls exceed the user-facing timeout guard, guiding users to retry or continue manually instead of seeing low-level errors.
  Job ad generation now also catches quota/time-limit issues and shows a bilingual retry hint rather than surfacing raw stack traces.
  A session-level quota guard now surfaces a bilingual warning and pauses further AI calls when the OpenAI account quota is exhausted, preventing repeated retries across the wizard.

- **AI skip controls for optional assistants**
  After repeated AI failures on the team advisor, skill expander, compensation assistant, or process planner, the wizard shows bilingual warnings with a “Skip AI for this step” action and surfaces skipped-assistant banners on the summary page so users can proceed manually.

- **Visible fallbacks for AI outages**
  Team advice, follow-up question cards, and salary estimates now surface bilingual notices and default suggestions whenever OpenAI calls fail or return empty results, so users understand what is missing and can continue manually.

- **Progress inbox with AI matching + deterministic fallback**
  Paste progress snippets from your hiring inbox and let the app map them to up to three tasks using structured OpenAI outputs (increment progress, mark done, add notes, or move subtasks). If AI is disabled or unavailable, deterministic matching keeps working so updates still apply.

- **Boolean search & exports**
  From the stored profile you can:
  - generate Boolean search strings,
  - assemble exportable job ads,
  - build interview guides and question sets.
  Summary tabs separate Role & search, Job ad, and Interview guide for quick review.
- **Preview + approval for AI outputs**
  Job ads, interview guides, and Boolean searches now render inside dedicated preview panels with bilingual “Approve & save” / “Discard” actions before they are written into the NeedAnalysisProfile or exported. Approved text stays fully editable for manual polishing.

- **AI transparency & auditability**
  AI-authored values are marked with 🤖 badges and tooltips (source, model, timestamp) in the form steps, list chips, and the summary panels. A dedicated change-log expander in the Summary step lists every field or list item the assistants created or modified during the session, so reviewers can double-check provenance before exporting.
- **Resilient autofill controls**
  Accept/reject decisions for AI autofill suggestions are tracked across steps, and the Company step now binds its dependencies defensively so autofill UI remains available even when optional helpers are missing. The compensation assistant now previews AI ranges against any existing manual values and asks for explicit acceptance (per field or in bulk) before overwriting data.
- **Autosave, export, and restore**
  Every profile edit and step completion refreshes an in-memory autosave snapshot (profile plus wizard state). Users can download the current JSON snapshot or import a saved one to recover work after a crash or browser reload.
- **Diary template with OneDrive export (separate tab)**
  Create bilingual daily journal entries mirroring the handwritten template (achievements, reactions, gratitude, focus), duplicate a new day with one click, preview Markdown, download locally, or upload directly to a shared OneDrive folder using `DIARY_ONEDRIVE_SHARED_URL` plus `ONEDRIVE_ACCESS_TOKEN`/`DIARY_ONEDRIVE_ACCESS_TOKEN`. The diary now lives on its own tab so the wizard’s final step continues to focus on the job ad, Boolean search, and interview exports.
- **Session-aware circuit breakers for external hints**
  Company enrichment calls to Clearbit and Wikipedia use per-session circuit breakers, preventing repeated failures from slowing down the wizard and surfacing bilingual notices when lookups are skipped.

## Error handling reference

See [`docs/ERROR_HANDLING.md`](docs/ERROR_HANDLING.md) for the current exception taxonomy, user-facing error messages, and the Chat → heuristics fallback chains used by the extraction and follow-up pipelines.

---

## Architecture overview

The repository is organized so that **schema**, **domain logic**, **LLM integration**, and **UI** are clearly separated:

- **Entry & configuration**
  - `app.py` – Streamlit entrypoint and global layout.
- `config.py`, `config_loader.py` – environment variables and feature flags (Responses vs. Chat, ChatKit on/off).
- `config/models.py` – centralized model defaults and routing (fixed `gpt-5.1-mini` with automatic GPT‑5.2 escalation; UI overrides and mode toggles are removed).
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
    - `pipelines/workflow.py` – lightweight workflow runner capturing task dependencies, retries, per-step status, and
      parallel execution for independent calls.
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
  - `utils/logging_context.py` – structured logging context (session ID, wizard step, pipeline task, model) for correlating
    multi-step runs.
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

### Reset API mode and model defaults

- **English:** Model selection now defaults to `gpt-4o-mini` with fallbacks through `gpt-4o` and `gpt-3.5-turbo` before escalating to GPT-5.2. Environment and secret overrides (`OPENAI_MODEL`, `DEFAULT_MODEL`, `LIGHTWEIGHT_MODEL`, `MEDIUM_REASONING_MODEL`, `HIGH_REASONING_MODEL`) are honoured again so deployments can choose cheaper or enterprise tiers; `python -m cli.reset_api_flags` still cleans legacy API flags such as `OPENAI_BASE_URL`/`OPENAI_API_BASE_URL`.
- **Deutsch:** Die Modellauswahl nutzt standardmäßig `gpt-4o-mini` und fällt bei Bedarf über `gpt-4o` und `gpt-3.5-turbo` zurück, bevor auf GPT-5.2 eskaliert wird. Umgebungsvariablen und Secrets (`OPENAI_MODEL`, `DEFAULT_MODEL`, `LIGHTWEIGHT_MODEL`, `MEDIUM_REASONING_MODEL`, `HIGH_REASONING_MODEL`) werden wieder berücksichtigt, damit Deployments günstigere oder Enterprise-Tiers wählen können; `python -m cli.reset_api_flags` bereinigt weiterhin alte API-Flags wie `OPENAI_BASE_URL`/`OPENAI_API_BASE_URL`.
- **English:** Model constants, aliases, routing, and fallbacks live in `config/models.py` as the single source of truth—update model names or defaults only there.
- **Deutsch:** Modellkonstanten, Aliase, Routing und Fallback-Ketten liegen zentral in `config/models.py`; passe Modellnamen oder Defaults nur dort an.
- **English:** Fallback order now prefers `gpt-4o-mini` → `gpt-4o` → `gpt-3.5-turbo` before escalating to GPT-5.2 tiers for resilience.
- **Deutsch:** Die Fallback-Reihenfolge bevorzugt jetzt `gpt-4o-mini` → `gpt-4o` → `gpt-3.5-turbo`, bevor bei Bedarf auf GPT-5.2 eskaliert wird.

### Quickstart for devs (English / Deutsch)

1. `poetry install` – install all dependencies into the virtual environment.
2. Export `OPENAI_API_KEY=<your key>` (or configure it via `.env`/`st.secrets`). Without a key the UI keeps AI-triggered widgets disabled.
3. `streamlit run app.py` – launches the wizard at http://localhost:8501.
4. Optional / Optional: set `OPENAI_API_BASE_URL=https://eu.api.openai.com/v1` if you need the EU endpoint.
5. Optional / Optional: set `OPENAI_SESSION_TOKEN_LIMIT=<tokens>` (alias: `OPENAI_TOKEN_BUDGET`) to enable the session budget guard. The app blocks further OpenAI calls and surfaces a bilingual warning once the cap is reached.

### Caching & retries (English / Deutsch)

- **English:** Expensive operations such as structured extraction use `st.cache_data` to avoid duplicate OpenAI calls, but fatal errors purge the cache entry so re-runs with the same inputs will retry instead of raising a cached exception. If you still encounter stale data, rerun the step after adjusting the form or clearing Streamlit’s cache via the menu.
- **Deutsch:** Aufwendige Operationen wie die strukturierte Extraktion nutzen `st.cache_data`, um doppelte OpenAI-Aufrufe zu vermeiden. Tritt dabei ein schwerer Fehler auf, wird der Cache-Eintrag gelöscht, sodass erneute Durchläufe mit denselben Eingaben einen frischen Versuch starten statt eine gecachte Ausnahme erneut auszulösen. Falls dennoch veraltete Daten auftauchen, wiederhole den Schritt nach einer Formularänderung oder leere den Streamlit-Cache über das Menü.

## LLM Configuration & Capabilities

Model routing and schema rules live in `config/models.py`. Lightweight chat models (`gpt-4o-mini`) handle extraction and schema repair, while longer-form generators default to `gpt-4o` with precise mode escalating to `o3-mini`. Structured calls rely on `response_format=json_schema` unless a task explicitly opts out. The lowest reasoning tier now defaults to `none` (alias: `minimal`) and is sent as `reasoning: {effort: "none"}` for GPT-4o compatibility; Responses payloads include the current verbosity hint except when the target model is a GPT-5 Codex variant.

| Task | Default model | Structured output? |
| --- | --- | --- |
| Extraction / Company info / JSON repair | `gpt-4o-mini` | JSON schema via `response_format=json_schema` |
| Follow-up questions / Team advice | `gpt-4o` | Text only (no JSON schema) |
| Job ad / Interview guide / Profile summary | `gpt-4o` (precise → `o3-mini`) | Text/Markdown |
| Embeddings (vector store) | `text-embedding-3-large` | Not applicable |

For detailed debugging steps, `response_format.schema` remedies, and test commands, see [docs/llm_config_and_debugging.md](docs/llm_config_and_debugging.md).

### Testing

- **Unit test suite (default) / Unit-Tests (Standard):**
  - `poetry run pytest`
  - `pytest.ini` applies `-m "not llm and not integration"` by default, so the standard run covers fast unit tests only.
- **Integration flows with mocked/recorded OpenAI responses / Integrations-Tests mit Mocks:**
  - Many end-to-end wizard and extraction flows stub the OpenAI client (for example `tests/test_integration_extraction_real_ads.py` monkeypatches `pipelines.need_analysis._extract_json_outcome` to return fixture payloads), so they can run offline without hitting the API.
  - Run them with `poetry run pytest --override-ini "addopts=" -m "integration and not llm"` to include all integration-marked tests while still skipping live-LLM cases.
- **Live LLM coverage / Tests mit echtem OpenAI-Schlüssel:**
  - Only needed when validating real Responses/Chat behaviour. Provide a real `OPENAI_API_KEY` and run `poetry run pytest --override-ini "addopts=" -m "llm"` (or combine with `integration` markers) knowing these calls may incur cost and rate limits.
- **Environment notes / Hinweise zur Umgebung:**
  - `tests/conftest.py` injects `OPENAI_API_KEY="test-key"` and enables `LLM_ENABLED` for most tests, so dummy keys are sufficient unless you explicitly opt into `-m llm`.
  - CI mirrors the commands above: the default job runs `poetry run pytest` (unit only), while integration or LLM jobs should drop the default `addopts` filter as shown.

### Developer references

- [Schema versioning and migrations](docs/SCHEMA_VERSIONING.md) – how to bump `schema_version`, write migration steps, and keep profile imports compatible.
