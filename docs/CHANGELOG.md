
---

## `docs/CHANGELOG.md`

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format roughly follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to follow [Semantic Versioning](https://semver.org/) when cutting tagged releases.

## [Unreleased]

### Added
- Dynamic-flow planning artifacts outlining the conditional NeedAnalysis roadmap (`docs/dynamic_flow_plan.md` and `docs/dynamic_flow_tasks.json`).
- Required-field ownership validation to keep `wizard_pages` metadata aligned with `PAGE_FOLLOWUP_PREFIXES`, plus supporting tests and documentation.
- Session-level OpenAI token budget guard configurable via `OPENAI_SESSION_TOKEN_LIMIT`/`OPENAI_TOKEN_BUDGET`; further calls are blocked with a bilingual warning once the cap is exceeded.
- Documented cost controls and low-cost model routing examples (including `MODEL_ROUTING__<task>` overrides and sidebar token usage references) in the README and LLM configuration guide.
- Bilingual extraction fallback banner on the Company step when `meta.extraction_fallback_active` is set so recruiters know to validate prefilled fields.
- Progress inbox on the Summary step now uses structured OpenAI outputs (when enabled) to map inbox updates to up to three tasks with progress, completion, or note actions; deterministic matching remains as the fallback when AI is unavailable.
- Summary Edit now supports core company and team field updates via a dedicated profile editor component.
- Summary Edit adds role/task and skills editing for responsibilities, requirements, and certificates in the Edit tab.
- Summary Edit now includes compensation and hiring process fields so salary and interview details can be adjusted in-place.
- Missing-field detection helpers in `wizard/missing_fields.py` with unit coverage.
- Step-level status helpers for missing required vs. critical fields in `wizard/step_status.py` with unit coverage.
- Step layout helper for consistent Known/Missing tabs with an optional tools expander.
- Wizard step registry metadata with ordered keys for shared navigation references.
- Feature-flagged sidebar stepper that summarizes per-step missing fields in the sidebar.
- Sidebar stepper navigation flag (`feature.sidebar_stepper_nav_v1`) to let users jump back to previous steps.

### Changed
- Sidebar settings now include an intro banner toggle that also hides the onboarding hero, clearer language labels, and an advanced expander for LLM-related options.
- Responsibility brainstormer suggestions now render in a sidebar checklist with bulk apply/dismiss controls instead of inline buttons, reducing main-form scrolling and delaying persistence until confirmation.
- Summary step now uses Overview/Edit/Exports/Warnings tabs, with per-step missing required/critical fields surfaced in the Warnings tab.
- Summary exports now centralize downloads in a compact artifact list, keeping export buttons in the Exports tab.
- Background hero image processing is now cached per theme to avoid repeated processing on reruns.
- Hero/banner styling now relies on shared theme tokens for backgrounds, borders, spacing, and typography so onboarding and global headers remain consistent across dark/light modes.
- Onboarding source inputs now render URL and upload options as separate panels with an OR divider, token-based focus rings, and responsive stacking for mobile screens.
- Onboarding now renders a single hero block above the URL/upload call-to-action while the global banner is suppressed on the onboarding step to avoid stacked headers.
- Onboarding hero copy now uses a human-centric headline, adds a primary CTA with a three-step timeline, and aligns product naming to Cognitive Staffing — Recruitment Need Analysis.
- Onboarding copy now follows a unified value-prop → action narrative with aligned DE/EN terminology across the global banner and job-ad intake step.
- Onboarding URL/upload inputs now use the `.onboarding-source-inputs` theme class for the two-column-to-stacked responsive layout.
- Location follow-up fields now map to the Company step in prefix-based routing to match where the inputs are rendered.
- Department follow-up fields (`department.*`) now belong to the Company step so required badges and targeted prompts render where the inputs live.
- Location follow-up fields (`location.*`) now belong to the Company step so missing prompts appear alongside the company location inputs.
- Position team follow-up fields (`position.team_*`) now route to the Company step to match the team structure inputs.
- GPT-5.2 tuning: job ad and interview-guide prompts now include short outlining steps, medium reasoning routes through `gpt-5.2-mini`, and long-form calls request richer sections to avoid terse bilingual outputs while keeping schemas intact.
- Default reasoning effort now initializes to `none` when no override is set; legacy `minimal` inputs are mapped to `effort: none` in API payloads, and verbosity hints are forwarded via Responses calls except for GPT-5 Codex models.
- Added a cost-saver sidebar toggle to force lightweight model routing and clamp `max_completion_tokens` for cheaper responses, while still allowing explicit model overrides when callers set them directly.
- Stage runtime output token caps default to 1024 (down from 2048) with OpenAI usage logging to track savings without truncating schema outputs.
- Default LLM routing now prefers `gpt-4o-mini` for lightweight and standard tasks, falls back through `gpt-4o` and `gpt-3.5-turbo`, and only escalates to GPT-5.2 tiers when needed; Quick/Precise toggles stay internal but environment and secret overrides (`OPENAI_MODEL`, `DEFAULT_MODEL`, `LIGHTWEIGHT_MODEL`, `MEDIUM_REASONING_MODEL`, `HIGH_REASONING_MODEL`) are supported again.
- Lightweight task routing keeps JSON repair, salary checks, extraction, and progress inbox calls on the cheaper `gpt-4o-mini`/`gpt-4o` path before considering higher-cost models.
- OpenAI SDK upgraded to the latest Responses-enabled release with first-class support for the `gpt-5.2` family (including mini/nano variants) and explicit routing through `responses.create` for structured calls.
- Model routing and task capabilities now live in a single `MODEL_CONFIG` map (model preference + JSON/text flags) inside `config/models.py`, eliminating scattered per-pipeline overrides and repeated fallback chains.
- Structured calls default to the Responses API (`responses.create`) with automatic fallbacks to Chat Completions when models reject Responses payloads or require tool/function calls outside the allowed configuration.
- Sidebar step preview now expands list-style requirements, responsibilities, and benefits into individual entries so the data point count reflects each item instead of a single joined preview.
- Auto-repair warning panels now render as a collapsed drawer pinned to the bottom of each step to keep the main form content visible.
- Structured extraction and JSON repair now call the Chat Completions API directly with JSON schemas, removing the Responses → Chat fallback hop to reduce noise and latency.
- Consolidated model constants, aliases, and routing logic into `config/models.py` to keep overrides in one place.
- Primary model selection defaults to `gpt-4o-mini` but can be overridden for deployments that require different cost/quality trade-offs.
- Removed the model selection dropdown from the extraction settings; the UI now relies solely on the default routing chain without surfacing `model_override` state.
- The strict JSON extraction toggle was removed from the UI; strict parsing now stays enabled by default and relies on automatic repair/fallback flows when payloads are invalid.
- Team & Structure now enforces the job title as a required field and keeps the AI team advisor disabled until job title and reporting-line details are available, preventing empty prompts from running.
- Company step now uses the shared Known/Missing step layout with a dedicated tools expander for assistants.
- Team & Structure step now uses the shared Known/Missing step layout with a dedicated tools expander for assistants.

### Removed
- Diary template and OneDrive upload tab have been retired; the landing page now focuses solely on the wizard and export flows.

### Fixed
- Team & Structure missing-tab follow-ups no longer re-render the reporting-line input, preventing the follow-up widget from overwriting a value already set in the main form.
- OpenAI timeouts now trigger a one-shot fallback to the next model with a friendly "taking longer" notice instead of looping on the stalled tier.
- Background thread pools now propagate the active session logging context so session identifiers stay visible inside worker logs.
- OpenAI quota exhaustion now sets a session-level circuit breaker: retries stop immediately, a bilingual availability warning appears, and further AI-triggered actions are disabled to avoid repeated 429 failures.
- Reduced-motion preferences now disable follow-up highlight animations in both themes for accessibility.
- Wizard navigation now shows a single centered Back/Next row at the bottom of each step instead of duplicated controls.
- Wizard navigation enforces the canonical eight-step order, ignores unknown query parameters, and keeps Next disabled when required fields are missing so steps no longer skip or repeat.
- Resolved Streamlit startup ImportError by importing the sidebar module explicitly before calling `render_sidebar`, preventing rerun crashes.
- Streamlit step headers no longer crash on missing-field badges; column ratios are fully numeric again.
- Step layout rendering now accepts pre-localized strings as well as `(de, en)` tuples, avoiding tuple-unpacking errors in the Team step.
- NeedAnalysisProfile canonicalization now rebuilds missing or invalid `requirements.skill_mappings` buckets and maps legacy keys (for example, `role.title`) to canonical fields before validation so extraction no longer triggers JSON repairs for empty company/position sections.
- JSON extraction fallback now applies additional heuristics (trailing comma cleanup, unterminated string repair, and largest-block extraction) before triggering one schema-guided repair call; it only returns a default profile after both parsing and repair fail and sets `meta.extraction_fallback_active` so the wizard can warn users when recovery was needed.
- Company step now binds autofill suggestion rendering from the wizard flow and skips the UI gracefully if the helper is unavailable, eliminating repeated dependency warnings and missing-suggestion regressions.
- Job ad generation errors (for example, rate limits) now render a bilingual retry hint instead of bubbling raw stack traces, keeping the final wizard step usable.
- Team advisor failures now surface a bilingual “assistant unavailable” notice without blocking navigation to the next step, preventing loops when rate limits occur.
- Follow-up question cards and salary estimates now display bilingual fallback notices plus default prompts when OpenAI calls fail or return empty responses, so users understand when AI content could not be delivered.
- Structured extraction cache entries now clear themselves when a fatal error occurs, preventing stale exceptions from being replayed on subsequent retries with unchanged inputs.

## [1.2.0] – 2025-02-24

### Changed
- Documented GPT-5 defaults: Quick/Schnell mode now highlights `gpt-5.1-mini` and Precise/Genau escalates to `gpt-5.1` with `o4-mini`/`o3` fallbacks; sample environment variables align with the new routing.
- Clarified DE/EN section mapping: benefits and hiring-process bullets are now documented as fully mapped into `compensation.benefits` and `process.hiring_process` after extraction.

### Fixed
- Updated developer/UI copy to remove stale `gpt-4.x` references and keep model override guidance consistent across README, .env examples, and the extraction settings panel.

### Added
- Lightweight workflow engine (`pipelines/workflow.py`) to orchestrate dependent LLM calls with retries and status tracking, now wiring the extraction and follow-up steps for UI progress reporting.
- Highlight and tracking of missing or critical fields per wizard step to drive follow-up questions and assistive UX.
- Documentation refresh for `README.md`, `AGENTS.md`, and this changelog to better support Codex‑style task generation and contributor onboarding.
- Testing quickstart covering Streamlit setup plus unit vs. integration runs with mocked OpenAI responses (see README “Testing”).
- Additional notes on Responses vs. Chat Completions routing and model overrides (`LIGHTWEIGHT_MODEL`, `MEDIUM_REASONING_MODEL`, `HIGH_REASONING_MODEL`).
- Clarified expectations for ChatKit workflows and assistant roles in `agent_setup.py` and `AGENTS.md`.
- CLI helper `python -m cli.reset_api_flags` to strip model and API mode overrides from `.env` files, plus README guidance on clearing legacy flags.
- Per-session circuit breaker utility guarding external enrichment (Clearbit/Wikipedia) with UI notices when lookups are skipped.
- Schema versioning for NeedAnalysisProfile plus migration helpers to stabilise autosave and import of legacy profiles.
- Session autosave snapshots with JSON export/import controls to recover NeedAnalysisProfile progress.
- Friendly bilingual loading spinners and timeout messaging for LLM-driven extraction steps so users see progress and retry hints instead of raw errors when calls run long.
- Per-step AI failure tracking with skip affordances for team, skills, compensation, and process assistants, including summary banners when AI content was skipped.
- Preview-and-approval flow for job ads, interview guides, and Boolean searches with bilingual preview panels and explicit Approve/Discard actions before persisting generated text into the NeedAnalysisProfile.
- AI contribution audit trail surfaced in the wizard: 🤖 badges with provenance tooltips on fields/list items and a summary change-log expander capturing source/model/timestamp for AI-authored values.

### Changed
- Tightened wording and structure of README “Architecture overview” and “Configuration” sections to reflect current directory layout and environment flags.
- Wizard steps now surface warning badges, bilingual summaries, and inline label/tooltips for missing critical fields, improving visibility before export.
- Wizard layout is now mobile-friendly with narrower content width, column wrap rules for 3+ column rows, duplicated navigation controls at the top of each step, and scroll-safe containers for wide tables/text inputs.
- Consolidated contributor expectations (formatting, type checking, testing, schema propagation) into `CONTRIBUTING.md` + `AGENTS.md`, referenced from README.
- Improved documentation around how NeedAnalysisProfile schema, Pydantic models, and LLM response schemas must stay in sync.
- Refactored the OpenAI API facade to orchestrate the shared client/payload/schema/tool helpers and added unit coverage for the new components.
- Strengthened structured extraction prompts with clearer bilingual section mapping (Aufgaben/Hauptaufgaben → responsibilities, Anforderungen/Profil/Voraussetzungen → requirements) and benefit/process reminders to reduce missed German bullets.
- Default LLM routing now prefers `gpt-5.1-mini` (with GPT-5.1/GPT-4 fallbacks) for quick tasks and medium reasoning tiers to reduce cost while preserving resilience.
- Added rule-based section markers in extraction prompts so German headings are annotated with English cues, improving recall of responsibilities and requirements lists.
- Expanded benefits and hiring-process detection (e.g., "Wir bieten", "Bewerbungsprozess") so compensation.benefits and process.hiring_process consistently capture enumerated perks and interview stages during extraction.
- Introduced structured error classes for OpenAI interactions and wizard flows to distinguish schema validation, response formatting, and external dependency failures.
- Workflow runner now schedules independent tasks in parallel with a thread-safe context to cut down perceived latency and comes with regression coverage for concurrent execution.
- Structured logging now includes session IDs, wizard step markers, pipeline task names, and active model metadata to simplify correlating multi-step failures in logs.
- The compensation assistant now shows bilingual overwrite confirmations (current vs. AI suggestion) and records accept/reject choices before applying salary ranges to existing manual inputs.

### Fixed
- Wizard navigation now maps seniority, compensation, remote-percentage, and interview-stage fields to their respective steps so "Next" only blocks on fields that belong to the current section.
- Company step no longer raises an AttributeError when binding autofill helpers; missing flow dependencies are logged and autofill rejection tracking remains available.
- Team step toggle tooltips for overtime, security clearance, and shift work now bind correctly, eliminating AttributeErrors and restoring help text visibility.
- Various small documentation inconsistencies (outdated model names or incomplete environment variable lists).
- Responses JSON schema now marks all object properties as required before hitting the Responses API to avoid 400 errors and
  keep generated artifacts (schema files, exports, wizard types) in sync.
- Added recursive validation and sanitization for Responses JSON schemas (need analysis, pre-analysis, follow-up questions) to
  prevent invalid_json_schema errors and enforce property coverage in automated tests.
- Restored the dedicated missing-sections extraction prompt so retries no longer fall back to plain error strings.
- Stabilised structured JSON extraction by classifying repairs vs. failures, logging low-confidence recoveries, and adding tests
  for malformed payload recovery.

---

> ⚠️ Historical entries below are a reconstructed summary of previously shipped functionality, not an exhaustive log of every commit. For exact changes, consult Git history.

## [0.6.0] – 2025-XX-XX

### Added
- ChatKit‑based assistants for:
  - Follow‑up Q&A on missing critical fields per wizard step.
  - Company insights enrichment (industry, size, HQ, website, description).
  - Team composition suggestions (team size, reporting lines, org context).
  - Responsibilities brainstorming (role‑specific bullets with accept/reject).
  - Skills & requirements expansion (related skills, certifications, required vs. nice‑to‑have).
  - Compensation range suggestions (salary ranges, benefits).
  - Hiring process planning (stage sequence suggestions persisted to `process.hiring_process`).
- ESCO integration and reference data to enhance skill bucketing and salary hints.
- Support for Quick/Schnell vs. Precise/Genau modes with separate model tiers and cache keys.
- Enhanced summary exports:
  - Boolean search generation.
  - Job ad and interview guide tabs built from NeedAnalysisProfile.

### Changed
- Refined ingest pipeline to more reliably detect German and English headings for:
  - Responsibilities / tasks.
  - Profile / requirements.
  - Benefits / offer.
  - Hiring / interview process.
- Normalization pipeline updated to map extracted segments into:
  - responsibilities vs. requirements,
  - compensation and benefits fields,
  - process stages.

### Fixed
- Various edge cases where empty or malformed LLM responses could break downstream views.
- Streamlit rerun issues where wizard navigation could become blocked after an LLM error.

## [0.5.0] – 2024-XX-XX

### Added
- Initial eight‑step bilingual wizard:
  - Onboarding, Company, Team & Structure, Role & Tasks, Skills & Requirements, Compensation, Hiring Process, Summary.
- NeedAnalysisProfile schema (`schema/need_analysis.schema.json`) and corresponding Pydantic models.
- Ingest support for:
  - PDF and DOCX job ads.
  - Job ad URLs.
  - Plain pasted text.
- Basic AI extraction from job ads to NeedAnalysisProfile using OpenAI APIs.
- First version of exports:
  - JSON profile download.
  - Markdown/job ad exports.

### Changed
- Reorganized repository into:
  - `core/`, `schema/`, `models/`, `utils/` for domain and validation.
  - `openai_utils/`, `llm/`, `pipelines/`, `integrations/` for AI orchestration.
  - `wizard/`, `wizard_pages/`, `components/`, `ui_views/`, `sidebar/` for UI.
- Introduced environment‑driven configuration (`config.py`, `config_loader.py`).

### Fixed
- Streamlit session state initialization issues when jumping directly to mid‑wizard URLs.
- Several ingest bugs when parsing heavily formatted PDFs.

## [0.1.0] – 2023-XX-XX

### Added
- Initial public prototype of Cognitive Staffing:
  - Single‑page Streamlit app.
  - Manual form for entering hiring needs.
  - Basic job ad generation from structured input.
- MIT license.
- Basic project layout and CI bootstrap.

---

## Release process

When preparing a release:

1. Move items from **[Unreleased]** into a new version section, e.g. `## [0.7.0] – YYYY-MM-DD`.
2. Group changes under `Added`, `Changed`, `Fixed`, `Deprecated`, `Removed`, and `Security` as appropriate.
3. Keep entries high‑level and user‑facing:
   - Mention breaking schema changes, new wizard steps, or new assistants.
   - Link to relevant PRs or issues when helpful.
4. Tag the release in git: `git tag v0.7.0 && git push origin v0.7.0`.
