
---

## `docs/CHANGELOG.md`

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format roughly follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to follow [Semantic Versioning](https://semver.org/) when cutting tagged releases.

## [Unreleased]

### Added
- Highlight and tracking of missing or critical fields per wizard step to drive follow-up questions and assistive UX.
- Documentation refresh for `README.md`, `AGENTS.md`, and this changelog to better support Codex‑style task generation and contributor onboarding.
- Additional notes on Responses vs. Chat Completions routing and model overrides (`LIGHTWEIGHT_MODEL`, `MEDIUM_REASONING_MODEL`, `HIGH_REASONING_MODEL`).
- Clarified expectations for ChatKit workflows and assistant roles in `agent_setup.py` and `AGENTS.md`.
- CLI helper `python -m cli.reset_api_flags` to strip model and API mode overrides from `.env` files, plus README guidance on clearing legacy flags.

### Changed
- Tightened wording and structure of README “Architecture overview” and “Configuration” sections to reflect current directory layout and environment flags.
- Consolidated contributor expectations (formatting, type checking, testing, schema propagation) into `CONTRIBUTING.md` + `AGENTS.md`, referenced from README.
- Improved documentation around how NeedAnalysisProfile schema, Pydantic models, and LLM response schemas must stay in sync.

### Fixed
- Various small documentation inconsistencies (outdated model names or incomplete environment variable lists).
- Responses JSON schema now marks all object properties as required before hitting the Responses API to avoid 400 errors and
  keep generated artifacts (schema files, exports, wizard types) in sync.

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

