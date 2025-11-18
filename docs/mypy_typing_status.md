# Mypy Typing Status – October 2024

## Overview
- **Command:** `poetry run mypy --config-file pyproject.toml .`
- **Log:** See `docs/mypy_errors_2024-10-08.txt` for the full 342-error report prior to adding targeted ignores.
- **Goal:** Document modules with pre-existing typing issues and explain the temporary ignores that allow focused checks on modified code.
- **Import skips:** `streamlit`, `requests`, and `bs4` are covered by `follow_imports = "skip"` so missing upstream stubs do not mask first-party regressions. Drop the skips once official types are shipped or a local facade is introduced.
- **Latest result (2025-02-21):** After dropping the `tests.*` override and annotating shared fixtures/helpers, the command reports 144 errors concentrated in legacy wizard tests and OpenAI harnesses. 【2bc049†L1-L93】

## Temporary Mypy Ignores
The following table summarises the new ignore overrides added in `pyproject.toml`. Error counts originate from `docs/mypy_errors_2024-10-08.txt` and reflect the baseline before suppression.

| Module pattern | Error count | Notes |
| --- | ---: | --- |
| `ingest.*` | 3 | Legacy ingestion utilities rely on dynamically typed third-party clients. |
| `components.requirements_insights` | 2 | Uses implicit tuple returns from scoring helpers; annotate once helper contracts are final. |
| `llm.openai_responses` | 2 | Depends on telemetry span helpers that currently accept `Any`. |
| `models.need_analysis` | 1 | Pending cleanup of custom Pydantic validators to align with v2 semantics. |
| `cli.rebuild_vector_store` | 2 | The CLI path is blocked on the new vector store SDK typings. |
| `app` | 1 | Streamlit entry point backfills telemetry conditionally; convert to helper functions to type-check cleanly. |
| `nlp.entities` | 1 | Contains a redundant `# type: ignore` guard from earlier rapid prototyping. |
| `pages.*` | 10 | Wizard pages still import the legacy layout helpers; will be handled after the runner refactor. |

The `tests.*` override was removed on 2025-02-21 so that mypy now reports issues directly inside the suite; the progress log tracks the outstanding work.

### Progress Log

- **2025-02-14:** Dropped the `sidebar.*` override after annotating branding helpers and normalising RGB tuples so the module passes strict type checking.
- **2025-02-15:** `wizard_router` now type-checks without overrides after annotating the navigation helpers and aligning metadata imports.
- **2025-02-17:** Removed the `openai_utils.*` override after introducing typed request/response helpers and splitting the retry plumbing into reusable dataclasses.
- **2025-02-18:** Dropped the `wizard.runner` and `wizard.layout` overrides by introducing typed navigation enums and delegating button rendering to `wizard.layout.render_navigation_controls()`.
- **2025-02-21:** Removed the `tests.*` override after adding typed session fixtures and helper dataclasses; the suite now surfaces 144 mypy errors that document work remaining across wizard-facing tests. 【2bc049†L1-L93】
- **2025-02-24:** Introduced `utils.telemetry.OtlpConfig`, dropped the module override, and aligned OTLP exporter plumbing with typed parameters so telemetry now participates in the main mypy run.
- **2025-02-26:** Added typed profile payloads to `utils.normalization`, updated all call sites, and removed the override so the normalisation pipeline now participates in mypy.

### Completed Refactors – Error Counts & Follow-ups

| Module | Baseline errors (2024-10-08) | Current errors | Traceability | Follow-up steps |
| --- | ---: | ---: | --- | --- |
| `sidebar.*` | 14【0a28eb†L1-L2】 | 0 | PR #853 (`0b4b4db`) removed the ignore and tightened the salary helpers.【c2cece†L12-L18】 | Monitor the Streamlit API migration so the new typed widgets continue to match upstream stubs once `streamlit` ships official typing information. |
| `wizard_router` | 5【984e26†L1-L2】 | 0 | PR #938 (`9a2076c`/`4f5e17c`) annotated metadata helpers and enforced type-safe navigation maps.【6576a7†L13-L21】 | Track the upcoming page-layout split so the router enums can adopt `Literal` route IDs shared with `pages.*`. |
| `openai_utils.*` | 17【12199b†L1-L2】 | 0 | PR #952 (`84155ff`/`629a21a`) refactored the request/response plumbing to use typed helper dataclasses.【52349b†L7-L12】 | Fold the new telemetry span helper typings into `llm/openai_responses.py` once Responses-tooling launches. |
| `wizard.runner` | — (module added after the 2024-10-08 snapshot, so errors were not recorded) | 0 | PR #953 (`ce12ac4`/`39e2c8e`) aligned the runner state machine with typed enums and helpers.【52349b†L5-L9】 | Once the multi-tenant wizard modes land, extend the runner enums with TypedDict-backed payloads for each variant. |
| `wizard.layout` | 5 (recorded as `wizard/_layout.py` before the rename)【cfe5cf†L1-L2】 | 0 | PR #953 (`ce12ac4`) extracted typed button renderers and value sync logic.【52349b†L5-L9】 | Audit the new `wizard.layout.render_navigation_controls()` helper whenever additional component states are introduced. |
| `tests.*` | 354【a5c77a†L1-L2】 | 144 (mypy run from 2025-02-21) | PR #954 (`94d19e2`/`459d881`) typed the fixtures and re-enabled the suite so remaining failures surface in CI.【52349b†L3-L6】 | Split the 144 reported issues into follow-up tickets (focus first on wizard snapshots and OpenAI harness mocks). |
| `utils.telemetry` | 9【0f448f†L1-L2】 | 0 | PR #955 (`370ff9e`/`c6cfdaa`) introduced the `OtlpConfig` dataclass and removed dynamic attribute lookups.【52349b†L1-L6】 | Add coverage for OTLP exporter fallbacks so new optional fields stay typed. |
| `utils.normalization` | 4【fa4b9c†L1-L2】 | 0 | PR #956 (`88a8884`/`18bdf75`) added TypedDict payloads for normalization outputs and updated call sites.【52349b†L1-L4】 | Continue migrating downstream consumers (e.g., `wizard._logic`) to the typed payloads to avoid regressions when shapes change. |

## Strict modules

The following wizard modules now run with `disallow_untyped_defs` to keep newly touched helpers fully annotated:

- `wizard._agents`
- `wizard._logic`
- `wizard._openai_bridge`
- `wizard.interview_step`
- `wizard.wizard`

If a refactor temporarily removes annotations, add them back before committing or extend the override table only for the duration of your branch.

## Next Steps
1. Create focused tickets per module group (e.g., `openai_utils.*`, `wizard.*`) to replace legacy patterns with typed helpers.
2. When tackling each ticket, drop the corresponding ignore override and re-run `poetry run mypy --config-file pyproject.toml .`.
3. Track progress by updating this document and shrinking the ignore table until the overrides are no longer necessary.
