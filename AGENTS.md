# CognitiveStaffing – Agent Guide  (CS_AGENT/1.0)

## How to work
- Use these directories & keys consistently:
  - UI: `components/`, `pages/`
  - Core/domain logic: `core/`
  - LLM: `llm/` (OpenAI Responses API + tools)
  - NLP: `nlp/`
  - RAG: `ingest/` (OpenAI Vector Store)
  - Utils: `utils/`
- Schema propagation (greppable): `CS_SCHEMA_PROPAGATE`
  - When adding/changing a field, **change everywhere**: Pydantic schema ↔ logic ↔ UI ↔ exports.
- UI binding rules:
  - Read defaults via `wizard._logic.get_value()` – the profile in `st.session_state[StateKeys.PROFILE]` is the only source of truth.
  - Use schema paths (`company.name`, `location.primary_city`, …) as widget keys and wire widgets through `wizard.wizard.profile_*` helpers so `_update_profile` stays in sync.
- Never hardcode secrets. Read keys via `os.getenv` or `st.secrets["openai"]`.

## Commands to run (blocking checks)
- **Format/Lint:** `ruff format && ruff check`
- **Types:** `mypy --config-file pyproject.toml`
- **Tests:** `pytest -q` (use `-m "not integration"` for CI if internet is off)
- **App smoke:** `streamlit run app.py` → Verify Wizard Flow, Summary, Exports, ESCO skills mapping.
- **Pre-commit:** `pre-commit run --all-files` (installed in setup)

## API + Tools
- **OpenAI:** Use **Responses API** with tools (`web_search`, `file_search`) and **Structured outputs** for JSON/Pydantic validation. Prefer `gpt-4o(-mini)` for low cost, use `o3-mini` when you need deeper reasoning (see `REASONING_EFFORT`). :contentReference[oaicite:1]{index=1}
- **Agents SDK:** If you change tools or agent wiring, update `agent_setup.py`. Hosted tools allowed: `WebSearchTool`, `FileSearchTool`. :contentReference[oaicite:2]{index=2}
- **RAG / Vector Store:** if `VECTOR_STORE_ID` set, use OpenAI Vector Stores search; otherwise run without retrieval. :contentReference[oaicite:3]{index=3}
- **ESCO API:** Use read-only GET endpoints from `https://ec.europa.eu/esco/api`. Cache with `st.cache_data` + TTL. :contentReference[oaicite:4]{index=4}

## Internet policy (Codex cloud tasks)
- **Default:** Internet OFF while agent runs. For dependency install during setup, internet is always ON.
- Enable agent internet only if needed. If enabled, allowlist domains + restrict methods (`GET`, `HEAD`, `OPTIONS`) unless integration tests require POST. :contentReference[oaicite:5]{index=5}

## What to output
- Include: (1) diff and file list, (2) commands run and failing logs, (3) repro & expected vs actual, (4) how to roll back.
- For big tasks, split into smaller PRs. :contentReference[oaicite:6]{index=6}

## Repo quick map (greppable IDs)
- `agent_setup.py` (CS_AGENT_SETUP): defines hosted tools + function tools for the Recruitment Wizard.
- `config.py` (CS_CONFIG): centralizes OpenAI model, timeout, base URL, `VECTOR_STORE_ID`, and `REASONING_EFFORT`.
- `pyproject.toml` (CS_PYPROJ): ruff/black/mypy/pytest configuration.
