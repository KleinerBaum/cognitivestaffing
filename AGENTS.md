# AGENTS.md — Vacalyser

## Scope
- Python 3.12, Streamlit app in `app.py` and `vacalyser/**`
- Do not add new external services or domains. Use the in-code SafeSession wrapper.

## Commands to run before proposing a diff
1. Ruff (fix in place): `ruff check --fix .`
2. Flake8: `flake8 .`
3. Tests (offline by default): `pytest -q`  
   - If you must exercise LLM calls, set `VACAYSER_OFFLINE=0` and ensure `OPENAI_API_KEY` is present.

## Network & Security
- Only call allowed domains: `api.openai.com`, `ec.europa.eu` (ESCO), others explicitly mentioned in code.
- No `curl`/`wget` to unlisted domains.
- Do not print env variables. Never log secrets.

## PR expectations
- Include a short rationale, what was tested, and how to reproduce locally.
