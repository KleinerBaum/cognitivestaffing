# Contributing to Cognitive Staffing

Welcome! This guide summarizes the core expectations for contributors. Please read `docs/DEV_GUIDE.md` for detailed instructions on adding wizard steps, follow-up questions, and schema propagation.

## Coding style
- Use Python ≥ 3.11 and follow PEP 8.
- Include type hints on all new/updated Python code.
- Keep secrets out of code; load keys via `os.getenv` or `st.secrets`.

## Quality checks
Run these commands before opening a PR:
- Format & lint: `ruff format && ruff check`
- Type-check: `mypy --config-file pyproject.toml`
- Tests: `pytest -q` (or `-m "not integration"` when offline)

## Branching & pull requests
- Create feature branches as `feat/<short-description>`.
- Open PRs against `dev` (no direct merges to `main`).
- Include release notes and update `docs/CHANGELOG.md` for user-facing or developer-impacting changes.

## Workflow tips
- Run `python scripts/propagate_schema.py --apply` after schema field changes to keep JSON schema and UI/export logic aligned.
- Use `python scripts/check_localization.py` when adding UI copy to ensure English/German coverage.
- The wizard cache and Boolean builder depend on the Quick vs. Precise mode; keep mode-aware behaviour intact when changing LLM routing.
