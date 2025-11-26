
---

## `docs/CHANGELOG.md`

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format roughly follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to follow [Semantic Versioning](https://semver.org/) when cutting tagged releases.

## [Unreleased]

### Added
- Lightweight workflow engine (`pipelines/workflow.py`) to orchestrate dependent LLM calls with retries and status tracking, now wiring the extraction and follow-up steps for UI progress reporting.
- Highlight and tracking of missing or critical fields per wizard step to drive follow-up questions and assistive UX.
- Documentation refresh for `README.md`, `AGENTS.md`, and this changelog to better support Codex‑style task generation and contributor onboarding.
- Additional notes on Responses vs. Chat Completions routing and model overrides (`LIGHTWEIGHT_MODEL`, `MEDIUM_REASONING_MODEL`, `HIGH_REASONING_MODEL`).
- Clarified expectations for ChatKit workflows and assistant roles in `agent_setup.py` and `AGENTS.md`.
- CLI helper `python -m cli.reset_api_flags` to strip model and API mode overrides from `.env` files, plus README guidance on clearing legacy flags.
- Per-session circuit breaker utility guarding external enrichment (Clearbit/Wikipedia) with UI notices when lookups are skipped.
- Schema versioning for NeedAnalysisProfile plus migration helpers to stabilise autosave and import of legacy profiles.

### Changed
- Tightened wording and structure of README “Architecture overview” and “Configuration” sections to reflect current directory layout and environment flags.
- Wizard steps now surface warning badges, bilingual summaries, and inline label/tooltips for missing critical fields, improving visibility before export.
- Consolidated contributor expectations (formatting, type checking, testing, schema propagation) into `CONTRIBUTING.md` + `AGENTS.md`, referenced from README.
- Improved documentation around how NeedAnalysisProfile schema, Pydantic models, and LLM response schemas must stay in sync.
- Refactored the OpenAI API facade to orchestrate the shared client/payload/schema/tool helpers and added unit coverage for the new components.
- Introduced structured error classes for OpenAI interactions and wizard flows to distinguish schema validation, response formatting, and external dependency failures.
- Workflow runner now schedules independent tasks in parallel with a thread-safe context to cut down perceived latency and comes with regression coverage for concurrent execution.
- Structured logging now includes session IDs, wizard step markers, pipeline task names, and active model metadata to simplify correlating multi-step failures in logs.

### Fixed
- Wizard navigation now maps seniority, compensation, remote-percentage, and interview-stage fields to their respective steps so "Next" only blocks on fields that belong to the current section.
- Company step no longer raises an AttributeError when binding autofill helpers; missing flow dependencies are logged and autofill rejection tracking remains available.
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

