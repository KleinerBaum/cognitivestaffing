# AGENTS.md

## Goal
This repo is a Streamlit wizard. Prefer small, reviewable PRs.
Do not change schema keys without updating schema + models + UI bindings.

## Setup
- Install deps: `poetry install`

## Tests
- Fast default: `poetry run pytest`
- Integration (mocked): `poetry run pytest --override-ini "addopts=" -m "integration and not llm"`
- LLM tests (cost): `poetry run pytest --override-ini "addopts=" -m "llm"` (only if asked)

## Run app
- `streamlit run app.py`

## Codebase discovery (use ripgrep)
- `rg -n "st\.tabs|wizard_router|current_step|step_" app.py wizard_router.py wizard wizard_pages sidebar ui_views`
- `rg -n "INLINE_FOLLOWUP_FIELDS|_render_inline_followups|_get_circuit_store|_get_assistant_state" -S`
- `rg -n "critical_fields\.json|question_logic" -S`

## PR conventions
- Include repro steps and test output.
- If a command fails, paste full logs/tracebacks.
