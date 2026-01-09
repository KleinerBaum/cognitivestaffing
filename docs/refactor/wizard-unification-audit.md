# Wizard unification audit (wizard/, wizard_pages/, wizard_tools/)

## Scope
This audit focuses on the wizard flow surfaces and metadata split across `wizard/`, `wizard_pages/`, and `wizard_tools/`, with a narrow goal: identify duplicated responsibilities, unused or only-test-touched modules/functions, and propose a staged refactor plan that unifies ownership without blocking delivery.

## Current sources of truth

| Concern | Primary source of truth | Secondary consumers / mirrors | Notes |
| --- | --- | --- | --- |
| Step ordering & canonical keys | `wizard_pages/__init__.py` → `WIZARD_PAGES` order | `wizard/flow.py` `STEP_SEQUENCE` + `legacy_index`; `wizard/step_registry.py` `STEPS`; `sidebar/__init__.py` `STEP_LABELS` + `PATH_PREFIX_STEP_MAP` | Multiple lists encode the same ordering and/or labels. `STEP_SEQUENCE` is still needed for renderers + legacy indexes, but order duplication risks drift. |
| Step UI renderers | `wizard/flow.py` `STEP_SEQUENCE` / `STEP_RENDERERS` | `wizard/steps/*` for some steps; inline `_step_*` functions in `wizard/flow.py` for others | Split between module-per-step and monolithic flow step functions; step wiring is centralized in `wizard/flow.py`. |
| Required fields (UI gating) | `wizard_pages/*.py` `required_fields` | `wizard/metadata.py` `PAGE_PROGRESS_FIELDS` adds `_PAGE_EXTRA_FIELDS` & virtual fields; tests rely on `validate_required_fields_by_page` | Required fields exist in metadata, but completion logic is rebuilt with extra fields and virtual markers. |
| Critical fields | `critical_fields.json` | `question_logic.py` loads as `CRITICAL_FIELDS`; `wizard/step_status.py` `load_critical_fields`; `wizard/flow.py` loads via `question_logic.CRITICAL_FIELDS` | Same JSON loaded in multiple places with different caching/filters. |
| Field → step ownership | `wizard/metadata.py` `PAGE_FOLLOWUP_PREFIXES`, `PAGE_SECTION_INDEXES`, `FIELD_SECTION_MAP` | `wizard/step_status.py` (via `field_belongs_to_page`), `wizard_router.py` (missing field logic) | Ownership rules are a mix of prefix routing and derived maps; any change requires validation updates. |
| Missing/validation rules | `wizard/metadata.py` `get_missing_critical_fields` + `_VALIDATED_CRITICAL_FIELDS` | `wizard_router.py` `_REQUIRED_FIELD_VALIDATORS`, `wizard/step_status.py` `compute_step_missing` | Validators for contact email and primary city are duplicated in router and metadata. |
| Wizard state keys | `constants/keys.py` `StateKeys` | `wizard/navigation_controller.py` & `sidebar/__init__.py` use literal `"current_step"` and session-state lookups | Mixed use of `StateKeys` and literal strings increases drift risk. |

## Duplication hotspots

1. **Step ordering & labels exist in three-plus places**
   - `WIZARD_PAGES` (ordering + labels) vs `STEP_SEQUENCE`/`STEP_RENDERERS` (ordering + legacy indexes) vs `wizard/step_registry.py` `STEPS` (ordering) vs `sidebar/__init__.py` `STEP_LABELS` (labels). The sidebar also keeps its own path-to-step map (`PATH_PREFIX_STEP_MAP`).

2. **Critical field logic duplicated between metadata and step status**
   - `question_logic.py` loads `critical_fields.json` into `CRITICAL_FIELDS` for follow-ups, while `wizard/step_status.py` loads the same JSON for missing-field counts. `wizard/metadata.py` has `get_missing_critical_fields` and separate validation logic for the same fields.

3. **Required field ownership is encoded in metadata and recalculated for completion**
   - `WizardPage.required_fields` is the canonical per-page list, but `PAGE_PROGRESS_FIELDS` (plus `_PAGE_EXTRA_FIELDS`) expands it for completion/validation. That expansion is separate from `wizard/step_status.py` and `wizard_router.py` missing/validation flow.

4. **Validation of key fields is duplicated**
   - `wizard_router.py` and `wizard/metadata.py` both register validators for contact email and primary city (`persist_contact_email`, `persist_primary_city`), meaning changes need to land in two modules.

5. **Follow-up/gap generation exists in both wizard flow and wizard tools**
   - `pipelines/followups.py` and `question_logic.py` drive live follow-ups in the wizard, while `wizard_tools/vacancy.py` exposes `detect_gaps` and `generate_followups` tool functions that are stubs/standalone. This creates two “sources of truth” for gap detection and follow-up phrasing.

## Unused code candidates (with evidence)

> Evidence includes the exact ripgrep commands and counts executed in the repo.

| Candidate | Evidence (command + count) | Why it looks unused or only-test-touched |
| --- | --- | --- |
| `wizard_tools/*` (graph/knowledge/execution/safety/vacancy tools) | `rg -n "wizard_tools" -g'!tests/*' -g'!wizard_tools/*'` → **4** results | Outside tests, `wizard_tools` imports show up in `agent_setup.py` and README; tool functions are not referenced by runtime wizard flow. |
| Graph tools (`add_stage`, `update_stage`, etc.) | `rg -n "add_stage|update_stage|remove_stage|connect_stages|disconnect|list_graph|save_graph|load_graph" -g'!wizard_tools/*' -g'!tests/*'` → **16** results | Only referenced in `agent_setup.py` for Agent tool wiring. No runtime wizard usage found. |
| Knowledge tools (`index_documents`, `semantic_search`, `attach_context`) | `rg -n "index_documents|semantic_search|attach_context" -g'!wizard_tools/*' -g'!tests/*'` → **6** results | Only referenced in `agent_setup.py` for hosted tools. |
| Vacancy tools (`upload_jobad`, `extract_vacancy_fields`, `detect_gaps`, etc.) | `rg -n "upload_jobad|extract_vacancy_fields|detect_gaps|generate_followups|ingest_answers|validate_profile|map_esco_skills|market_salary_enrich|generate_jd|export_profile" -g'!wizard_tools/*' -g'!tests/*'` → **33** results | Appear in `agent_setup.py` only; live wizard flow uses `pipelines/*` + `question_logic.py` instead. |
| `wizard/step_registry.py` | `rg -n "step_registry" -g'!wizard/step_registry.py'` → **6** results | Used by sidebar + tests + README, but duplicates `WIZARD_PAGES` ordering and `STEP_SEQUENCE`. Candidate for deprecation if the sidebar reads from `WIZARD_PAGES`. |

## Refactor plan (6–10 small PRs)

1. **PR 1 — Document canonical ownership + deprecation targets**
   - Add a short RFC (in `docs/refactor/`) that declares `WIZARD_PAGES` as the single source for ordering + labels.
   - Mark `wizard/step_registry.py` and `sidebar.__init__.STEP_LABELS` as legacy (TODO comment + doc pointer).

2. **PR 2 — Sidebar uses `WIZARD_PAGES` for labels + ordering**
   - Replace `STEP_LABELS` with `[(page.key, tr(*page.label)) for page in WIZARD_PAGES]`.
   - Keep `PATH_PREFIX_STEP_MAP` but source its keys from `PAGE_FOLLOWUP_PREFIXES` to avoid another manual list.

3. **PR 3 — Consolidate required-field completion map**
   - Move `_PAGE_EXTRA_FIELDS` and `PAGE_PROGRESS_FIELDS` into a dedicated helper that returns a typed mapping, and re-use it in both sidebar and router.
   - Ensure `validate_required_fields_by_page` remains the enforcement gate for required fields.

4. **PR 4 — Unify critical-field loading**
   - Introduce a single `wizard/critical_fields.py` loader with caching; re-use in `question_logic.py`, `wizard/step_status.py`, and `wizard/metadata.py`.
   - Keep JSON schema unchanged, just remove duplicate file reads and align filtering behavior.

5. **PR 5 — Consolidate missing-field calculations**
   - Define one missing-field computation API (e.g., `wizard/missing_fields.py`) that returns both required + critical per page.
   - Have `wizard_router.py`, `wizard/step_status.py`, and sidebar use that API so missing counts stay consistent.

6. **PR 6 — Validate state key usage**
   - Replace literal `"current_step"` strings with `StateKeys.STEP` in `wizard/navigation_controller.py` and `sidebar/__init__.py` (or alias with a typed constant to protect backward compatibility).

7. **PR 7 — Triage `wizard_tools` and decide runtime ownership**
   - Decide whether tool functions are part of the product or only for experimentation.
   - If production: wire tool calls to `pipelines/*`/`question_logic.py` (no stubs). If not: move them to `experiments/` or mark as deprecated.

8. **PR 8 — Replace `wizard/step_registry.py` with `WIZARD_PAGES` (or remove)**
   - Update sidebar and tests to assert ordering from `WIZARD_PAGES`.
   - Remove `step_registry.py` or keep a thin wrapper that re-exports `WIZARD_PAGES`-derived keys.

9. **PR 9 — Incremental UI step migration**
   - Complete the move of remaining `_step_*` renderers in `wizard/flow.py` into `wizard/steps/*` modules.
   - Keep `STEP_SEQUENCE` as the wiring layer until routing is migrated to a new step registry.

10. **PR 10 — Cleanup + tests**
    - Remove unused tests around deprecated modules, update docs (`docs/wizard_flow.md`) to reflect new ownership, and keep `tests/test_required_fields_mapping.py` aligned.

## Deprecation / migration summary

- **Step ordering:** Migrate sidebar + tests to `WIZARD_PAGES` and deprecate `wizard/step_registry.py` once consumers are updated.
- **Critical fields:** Standardize on one loader module shared across question logic + step status + metadata.
- **Follow-ups:** Reconcile `wizard_tools` stubs with the live pipeline (`pipelines/followups.py`, `question_logic.py`) or mark tools as non-production.
