
---

## `docs/CHANGELOG.md`

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format roughly follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to follow [Semantic Versioning](https://semver.org/) when cutting tagged releases.

## [Unreleased]

### Added
- Troubleshooting guidance for the common Streamlit ScriptRunContext warning and OTLP telemetry configuration.
- Business-Kontext wizard step with domain-first inputs, industry-code suggestions, and optional organisation/contact fields.
- Debug-only Mermaid flow diagram for the wizard router, rendered from the live step configuration when `DEBUG_FLOW_DIAGRAM` is enabled.
- `BusinessContext` schema section with migration/backfill helpers for legacy company/department data.
- Developer guide for adding wizard steps safely, including schema and test expectations (`docs/dev/wizard-steps.md`).
- Step-graph navigation hook (`next_step_id`) so steps can resolve dynamic next keys for branching flows.
- Shared Streamlit wizard UX kit module with a compatibility shim in `ui/`.
- Registry integrity test that validates step keys, required fields, and legacy indices alignment.
- Dynamic-flow planning artifacts outlining the conditional NeedAnalysis roadmap (`docs/dynamic_flow_plan.md` and `docs/dynamic_flow_tasks.json`).
- Form-based wizard panel fade mode toggle in `app.py`, rendering steps inside `st.form` with submit-driven navigation.
- Onboarding source context selection that branches into company or client detail steps without exposing both in the stepper.
- Canonical wizard services for gap detection and profile validation, shared by the UI flow and wizard tools.
- Conditional step activation predicates so inactive wizard steps are skipped in navigation and deep links.
- Required-field ownership validation to keep `wizard_pages` metadata aligned with `PAGE_FOLLOWUP_PREFIXES`, plus supporting tests and documentation.
- Session-level OpenAI token budget guard configurable via `OPENAI_SESSION_TOKEN_LIMIT`/`OPENAI_TOKEN_BUDGET`; further calls are blocked with a bilingual warning once the cap is exceeded.
- Documented cost controls and low-cost model routing examples (including `MODEL_ROUTING__<task>` overrides and sidebar token usage references) in the README and LLM configuration guide.
- Single-page wizard mode that renders all steps sequentially in expanders with a top-level missing-fields validation summary.
- Wizard unification maintainability audit covering wizard step metadata, renderers, and agent tools (`docs/refactor/wizard-unification-audit.md`).
- Bilingual extraction fallback banner on the Company step when `meta.extraction_fallback_active` is set so recruiters know to validate prefilled fields.
- Progress inbox on the Summary step now uses structured OpenAI outputs (when enabled) to map inbox updates to up to three tasks with progress, completion, or note actions; deterministic matching remains as the fallback when AI is unavailable.
- Summary Edit now supports core company and team field updates via a dedicated profile editor component.
- Summary Edit adds role/task and skills editing for responsibilities, requirements, and certificates in the Edit tab.
- Summary Edit now includes compensation and hiring process fields so salary and interview details can be adjusted in-place.
- Missing-field detection helpers in `wizard/missing_fields.py` with unit coverage.
- Step-level status helpers for missing required vs. critical fields in `wizard/step_status.py` with unit coverage.
- Step layout helper for consistent Known → Missing → Validate sections with an optional tools expander.
- Wizard step registry metadata with ordered keys for shared navigation references.
- Feature-flagged sidebar stepper that summarizes per-step missing fields in the sidebar.
- Sidebar stepper navigation flag (`feature.sidebar_stepper_nav_v1`) to let users jump back to previous steps.
- Deterministic Rheinbahn job ad fixture plus a tiny loader for regression tests.
- Streamlit AppTest regression coverage for the ESCO occupation selector to guard against widget state mutation errors.
- Rule field path validation tests to ensure rule-based extraction stays aligned with the NeedAnalysis schema.
- Wizard recovery UI now shows step-specific retry/reset controls plus a technical-details drawer with sanitized error context.
- Optional wizard step-panel fade flag (`WIZARD_STEP_FORM_FADE` or `wizard.step_form_fade` session key) plus origin badges for extracted/suggested fields.

### Removed
- Binary wizard UI screenshot asset removed from the repository to keep diffs lightweight.
- Job-ad extraction now surfaces a progress indicator that tracks structured extraction and follow-up generation.

### Changed
- Wizard step labels and headers now align to Company details → Department & Team → Tasks & Skills → Skills recap → Benefits → Recruitment process, with summary-first layouts and department/team inputs consolidated into the Department & Team step.
- Flow mode now defaults to and enforces the single-page wizard view, removing the guided multi-step toggle from the sidebar settings.
- OTLP telemetry bootstrap now logs missing endpoint configuration at debug level to reduce noise in local runs.
- Skill suggestion prompts now enforce JSON-only output with schema validation and repair before fallback parsing.
- ESCO occupation selector now initializes the widget key before render and syncs the selection back into the profile to prevent Streamlit session-state mutation errors.
- NeedAnalysis schema generation now enforces `required` arrays for every object (including map-like nodes) and adds a schema integrity test to prevent OpenAI `response_format` drift.
- Updated the German benefits prompt wording to use "Vorteile oder Zusatzleistungen."
- Startup model routing now selects and stores one resolved model per tier (FAST/QUALITY/LONG_CONTEXT) with explicit fallback chains for each tier.
- Wizard flow step 2 now focuses on Company details (business context + core company/location data), while department/team inputs live in the dedicated Department & Team step.
- `app.py` now renders the guided-flow UI kit stepper/context/progress elements and inline saved feedback to stabilize the baseline wizard UX.
- Wizard back navigation now prefers a history stack so branching paths return to the actual previous step.
- Company step headers and captions now adapt when the client branch is active.
- Wizard step ordering now aligns to the canonical eight-step flow while the Business-Kontext step switches to client labels for agency contexts.
- Wizard navigation now validates required fields on Next click without disabling the button, keeping navigation responsive while still blocking incomplete steps.
- Wizard navigation now renders an emoji stepper with active/done/upcoming styling, and the layout reserves space for validation messaging to prevent shifts.
- README now documents the reserved validation area and origin markers, and the UX preview text assets now cover the stepper, origin markers, and validation area in `images/`.
- Wizard step metadata and renderers now live in a single step registry, with legacy `wizard_pages` modules proxying the registry to avoid drift.
- Wizard navigation state now stores under a wizard-specific `wiz:<wizard_id>:` namespace with legacy aliasing for the default wizard session.
- Navigation validation warnings now render in a reserved inline area below the controls to avoid layout shifts.
- Wizard navigation logic now lives under `wizard/navigation/` (router, UI, state sync) with compatibility shims for legacy imports.
- Follow-up generation now routes through a single canonical service (`wizard/services/followups.py`) with structured outputs, and both the UI pipeline and wizard tools delegate to it for consistent schemas.
- OpenAI model list lookups, ESCO API responses (TTL), and job-ad extraction/follow-up results are now cached per session to cut repeated work during Streamlit reruns.
- Job description generation in `wizard_tools.generate_jd` now delegates to the shared job description service so the tool uses the same generator as the wizard UI.
- Stage graph utilities moved under `wizard_tools/experimental` and are only wired into agents when `ENABLE_AGENT_GRAPH` is enabled.
- Documented the onboarding hero structure (CTA anchor `#onboarding-source`, timeline classes), clarified the single-hero approach, and noted sidebar hero/stepper CSS now lives in the shared theme stylesheets.
- Sidebar hero/stepper styles now live in the shared theme stylesheets instead of inline injection in `app.py`.
- Sidebar settings now include an intro banner toggle that also hides the onboarding hero, clearer language labels, and an advanced expander for LLM-related options.
- Global hero/banner and its inline intro controls no longer render outside onboarding steps to keep later steps focused on the wizard form.
- Onboarding details expander copy now emphasizes process, privacy, and accuracy expectations, and the label uses a bilingual "Details & Einstellungen / Details & settings" title.
- Responsibility brainstormer suggestions now render in a sidebar checklist with bulk apply/dismiss controls instead of inline buttons, reducing main-form scrolling and delaying persistence until confirmation.
- Onboarding hero copy now uses refreshed bilingual eyebrow, headline, subheadline, CTA messaging, with updated three-step timeline wording.
- Summary step now uses Overview/Edit/Exports/Warnings tabs, with per-step missing required/critical fields surfaced in the Warnings tab.
- Summary exports now centralize downloads in a compact artifact list, keeping export buttons in the Exports tab.
- Background hero image processing is now cached per theme to avoid repeated processing on reruns.
- Hero/banner styling now relies on shared theme tokens for backgrounds, borders, spacing, and typography so onboarding and global headers remain consistent across dark/light modes.
- Onboarding hero styles now live in shared theme CSS, with hover micro-interactions and reduced-motion handling across dark/light themes.
- Onboarding source inputs now render URL and upload options as separate panels with an OR divider, token-based focus rings, and responsive stacking for mobile screens.
- Onboarding now renders a single hero block above the URL/upload call-to-action while the global banner is suppressed on the onboarding step to avoid stacked headers.
- Onboarding hero copy now uses a human-centric headline, adds a primary CTA with a three-step timeline, and aligns product naming to Cognitive Staffing — Recruitment Need Analysis.
- Onboarding copy now follows a unified value-prop → action narrative with aligned DE/EN terminology across the global banner and job-ad intake step.
- Onboarding URL/upload inputs now use the `.onboarding-source-inputs` theme class for the two-column-to-stacked responsive layout.
- Location follow-up fields now map to the Company details step in prefix-based routing to match where the inputs are rendered.
- Department follow-up fields (`department.*`) now belong to the Department & Team step so required badges and targeted prompts render where the inputs live.
- Location follow-up fields (`location.*`) now belong to the Company details step so missing prompts appear alongside the company location inputs.
- GPT-5.2 tuning: job ad and interview-guide prompts now include short outlining steps, medium reasoning routes through `gpt-5.2-mini`, and long-form calls request richer sections to avoid terse bilingual outputs while keeping schemas intact.
- Default reasoning effort now initializes to `none` when no override is set; legacy `minimal` inputs are mapped to `effort: none` in API payloads, and verbosity hints are forwarded via Responses calls except for GPT-5 Codex models.
- Cost-saver routing now downgrades QUALITY to FAST for non-critical tasks (job ads, document refinement, and final explanations stay on QUALITY), and still clamps `max_completion_tokens` for cheaper responses while respecting explicit model overrides.
- Runtime model routing now prefers GPT-5 tiers for web/file search tooling and falls back to `gpt-4.1-nano` for ultra-long prompts (>300k estimated tokens).
- Responses-vs-Chat gating no longer forces GPT-4.1 or GPT-5 families onto Chat Completions, keeping Responses features available on those models.
- Stage runtime output token caps default to 1024 (down from 2048) with OpenAI usage logging to track savings without truncating schema outputs.
- Model routing now uses FAST (`gpt-5-nano`), QUALITY (`gpt-5-mini`), and LONG_CONTEXT (`gpt-4.1-nano`) tiers, while PRECISE (`gpt-5.1`) only activates via the precise toggle or high reasoning effort.
- Default LLM routing now falls back through GPT-4o and GPT-3.5 tiers before escalating to GPT-5.2, keeping Quick/Precise toggles internal while honoring environment and secret overrides (`OPENAI_MODEL`, `DEFAULT_MODEL`, `LIGHTWEIGHT_MODEL`, `MEDIUM_REASONING_MODEL`, `HIGH_REASONING_MODEL`).
- Lightweight task routing keeps JSON repair, salary checks, and progress inbox calls on the FAST (`gpt-5-nano`) tier, while long-context extraction uses `gpt-4.1-nano` before considering higher-cost models.
- OpenAI SDK upgraded to the latest Responses-enabled release with first-class support for the `gpt-5.2` family (including mini/nano variants) and explicit routing through `responses.create` for structured calls.
- Model routing and task capabilities now live in a single `MODEL_CONFIG` map (model preference + JSON/text flags) inside `config/models.py`, eliminating scattered per-pipeline overrides and repeated fallback chains.
- Structured calls default to the Responses API (`responses.create`) with automatic fallbacks to Chat Completions when models reject Responses payloads or require tool/function calls outside the allowed configuration.
- Sidebar step preview now expands list-style requirements, responsibilities, and benefits into individual entries so the data point count reflects each item instead of a single joined preview.
- Auto-repair warning panels now render as a collapsed drawer pinned to the bottom of each step to keep the main form content visible.
- Structured extraction and JSON repair now call the Chat Completions API directly with JSON schemas, removing the Responses → Chat fallback hop to reduce noise and latency.
- Consolidated model constants, aliases, and routing logic into `config/models.py` to keep overrides in one place.
- Primary model selection defaults to `gpt-5-nano` but can be overridden for deployments that require different cost/quality trade-offs.
- Removed the model selection dropdown from the extraction settings; the UI now relies solely on the default routing chain without surfacing `model_override` state.
- The strict JSON extraction toggle was removed from the UI; strict parsing now stays enabled by default and relies on automatic repair/fallback flows when payloads are invalid.
- Team & Structure now enforces the job title as a required field and keeps the AI team advisor disabled until job title and reporting-line details are available, preventing empty prompts from running.
- Company details now use the shared summary-first Known/Missing/Validate step layout with a dedicated tools expander for assistants.
- Team & Structure step now uses the shared Known/Missing step layout with a dedicated tools expander for assistants.

### Removed
- Diary template and OneDrive upload tab have been retired; the landing page now focuses solely on the wizard and export flows.

### Fixed
- Benefit suggestion fallbacks now try the static shortlist first and only reach the legacy LLM when enabled (`ALLOW_LEGACY_FALLBACKS`).
- Suggestion helpers now guard chat-fallback logging to only touch `used_chat_fallback` on `ResponsesCallResult` responses, preventing type mismatches in tests or mocks.
- Wizard test stubs now provide Streamlit container context managers and three-column placeholders to match layout expectations.
- ESCO occupation selector now uses a dedicated widget session-state key to avoid Streamlit
  widget mutation errors while keeping profile state in sync.
- Wizard UI session-state keys now use wizard-scoped or app-scoped namespaces (via `wiz.k(...)`)
  to prevent collisions in multi-wizard or multi-repo deployments.
- Structured extraction now enforces JSON-only outputs, retries a schema-guided repair with validation errors, and records recovery metadata when malformed payloads are repaired.
- Follow-up generation now extracts JSON from fenced/prose outputs, retries with schema error context, and records internal error reasons when falling back to defaults.
- Team & Structure missing-tab follow-ups no longer re-render the reporting-line input, preventing the follow-up widget from overwriting a value already set in the main form.
- Follow-up generation now validates response schemas, retries once with strict JSON guidance, and surfaces clearer fallback notices when invalid payloads are returned.
- OpenAI timeouts now trigger a one-shot fallback to the next model with a friendly "taking longer" notice instead of looping on the stalled tier.
- Background thread pools now propagate the active session logging context so session identifiers stay visible inside worker logs.
- Background LLM calls now avoid touching Streamlit session/UI state, preventing missing ScriptRunContext warnings in threaded execution.
- OpenAI quota exhaustion now sets a session-level circuit breaker: retries stop immediately, a bilingual availability warning appears, and further AI-triggered actions are disabled to avoid repeated 429 failures.
- Company step flow dependency binding now treats the autofill suggestion helper as optional and logs missing optional helpers at debug level.
- Reduced-motion preferences now disable follow-up highlight animations in both themes for accessibility.
- Wizard navigation now shows a single centered Back/Next row at the bottom of each step instead of duplicated controls.
- Wizard navigation enforces the canonical eight-step order, ignores unknown query parameters, and keeps Next disabled when required fields are missing so steps no longer skip or repeat.
- Resolved Streamlit startup ImportError by importing the sidebar module explicitly before calling `render_sidebar`, preventing rerun crashes.
- Streamlit step headers no longer crash on missing-field badges; column ratios are fully numeric again.
- Step layout rendering now accepts pre-localized strings as well as `(de, en)` tuples, avoiding tuple-unpacking errors in the Team step.
- NeedAnalysisProfile canonicalization now rebuilds missing or invalid `requirements.skill_mappings` buckets and maps legacy keys (for example, `role.title`) to canonical fields before validation so extraction no longer triggers JSON repairs for empty company/position sections.
- JSON extraction fallback now applies additional heuristics (trailing comma cleanup, unterminated string repair, and largest-block extraction) before triggering one schema-guided repair call; it only returns a default profile after both parsing and repair fail and sets `meta.extraction_fallback_active` so the wizard can warn users when recovery was needed.
- Sidebar token usage tables now recognize per-task usage counters provided as nested input/output totals, ensuring summaries render whenever valid data is present.
- Structured extraction now performs a schema-guided JSON repair retry with exponential backoff before coercion, logging PII-safe error metadata and consistently setting `meta.extraction_fallback_active` when fallbacks are used.
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
