# Cognitive Staffing

Cognitive Staffing is a bilingual (DE/EN) Streamlit wizard that converts unstructured job ads into a structured `NeedAnalysisProfile`, then generates recruiter-ready outputs (job ad, interview guide, Boolean search, exports).

## Runtime policy (current)

- **Strict nano-only for non-embedding tasks:** all non-embedding model routing resolves to `gpt-5-nano` when `STRICT_NANO_ONLY=true`.
- **Responses-first integration:** OpenAI calls are routed through the Responses runtime first.
- **Structured outputs on Responses:** structured calls use **`text.format`** contracts.
- **Reasoning baseline:** `reasoning.effort="minimal"` is the default baseline.
- **Tools:** `RESPONSES_ALLOW_TOOLS=true` by default, with explicit guards against unsupported tool types for nano (`tool_search`, `computer_use`, `hosted_shell`, `apply_patch`, `skills`).
- **Embeddings:** embedding model remains separately configurable (for example `text-embedding-3-large`).

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
poetry install --with dev
cp .env.example .env
poetry run streamlit run app.py
```

## Minimal configuration

Set in `.env` or `.streamlit/secrets.toml`:

```env
OPENAI_API_KEY=<your-key>
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_REQUEST_TIMEOUT=120

STRICT_NANO_ONLY=true
OPENAI_MODEL=gpt-5-nano
DEFAULT_MODEL=gpt-5-nano
LIGHTWEIGHT_MODEL=gpt-5-nano
MEDIUM_REASONING_MODEL=gpt-5-nano
HIGH_REASONING_MODEL=gpt-5-nano
REASONING_EFFORT=minimal
VERBOSITY=low
RESPONSES_ALLOW_TOOLS=true
```

## Wizard-Version aktivieren

Die Runtime löst die aktive Wizard-Variante in dieser Reihenfolge auf: **Query-Param → Session-State → Env-Flag → Default**.

- **Query-Param (höchste Priorität):** `?wizard=v2` (alternativ akzeptiert: `wizard_version`, `flow`).
- **Env-Flag:** `ENABLE_WIZARD_V2=1` aktiviert V2, wenn kein Query/Session-Override gesetzt ist.

Beispiele:

```text
http://localhost:8501/?wizard=v2
```

```bash
ENABLE_WIZARD_V2=1 poetry run streamlit run app.py
```

## Wizard UI notes

- Multi-step navigation is owned by `wizard/navigation/router.py::NavigationController`; `wizard_router.py` only wraps rendering + control wiring.
- Wizard version resolution (V1/V2) is centralized in `wizard/step_registry_runtime.py` for query/session/env handling.
- In single-page mode, the global **Validate all steps** expander is hidden to reduce duplicate controls at the top of the page.
- The introductory **Welcome** panel is also hidden in single-page mode, and step headers use text-only status labels (no warning emojis).


## Metadata access (confidence/evidence)

- Use `state.ai_contributions.get_profile_metadata()` / `set_profile_metadata()` for all `StateKeys.PROFILE_METADATA` reads and writes.
- The access layer auto-migrates legacy containers (`field_confidence`, `rules`, `llm_recovery`, lock lists) into a canonical Pydantic envelope (`core/confidence.py`) and writes a legacy-compatible projection back to session state.

## Troubleshooting

- **Missing API key:** set `OPENAI_API_KEY` in env or Streamlit secrets.
- **Wrong model appears in logs:** ensure `STRICT_NANO_ONLY=true` and restart the app process.
- **Schema/structured output failures:** ensure structured calls use Responses `text.format` shape and strict JSON schema.
- **Follow-up schema contract:** canonical follow-up schema/validator/normalization lives in `llm/followup_contract.py` and is reused by the follow-up service parser.
- **`response_format` vs `text.format` confusion:** use `text.format` for Responses payloads; `response_format` is legacy/compatibility only.
- **Timeout/retry drift:** verify `OPENAI_REQUEST_TIMEOUT` and check runtime logs for explicit fallback mode markers.

## Schema versioning

- Canonical schema/model/adapters are registered in `core/schema_registry.py`.
- Source-of-Truth and ownership rules are documented in `docs/SCHEMA_VERSIONING.md`.

## Quality checks

```bash
ruff format .
ruff check .
mypy --config-file pyproject.toml
pytest -q
```
