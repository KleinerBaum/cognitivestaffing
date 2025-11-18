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
| `utils.telemetry` | 9 | Requires typed configuration objects for OTLP exporters. |
| `utils.normalization` | 3 | The schema normalization pipeline still mutates `NeedAnalysisProfile` instances dynamically. |
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
