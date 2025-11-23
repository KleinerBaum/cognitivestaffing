# Cognitive Staffing

Cognitive Staffing is a Streamlit wizard that converts unstructured job ads (PDFs, URLs, or pasted text) into a structured hiring profile and recruiter-ready outputs. It pairs rule-based ingest with OpenAI-powered extraction to prefill company, role, process, and compensation details, then guides users through eight bilingual steps to review, enrich, and export the results.

## Features
- **Eight-step wizard**: Onboarding → Company → Team & Structure → Role & Tasks → Skills & Requirements → Compensation → Hiring Process → Summary. Each step shows bilingual intros, validations, and inline follow-ups.
- **AI extraction & enrichment**: Ingest heuristics plus OpenAI Responses API map job ads into the NeedAnalysisProfile schema, highlight missing fields, and surface focused follow-up questions.
- **Quick vs. Precise modes**: The in-app toggle routes **Quick/Schnell** flows to `gpt-4o-mini` (fast, low reasoning effort) and **Precise/Genau** flows to higher reasoning models (for example `o3-mini`) via `REASONING_EFFORT`. Cache keys are mode-aware so switching modes refreshes results.
- **Responses vs. Chat API**: By default `USE_RESPONSES_API=1` keeps structured calls on the OpenAI Responses API; set `USE_CLASSIC_API=1` (or clear `USE_RESPONSES_API`) to force the legacy Chat Completions fallback. When Responses returns empty streams, the client cascades to Chat and then curated static suggestions.
- **Boolean search & exports**: Build Boolean strings, job ads, and interview guides directly from the stored profile. Summary tabs separate **Role tasks & search**, **Job ad**, and **Interview guide** for easy review.
- **ESCO integration**: Optional ESCO skill lookups (read-only GET) enrich extracted skills with cached taxonomy mappings.
- **Retried, structured outputs**: Strict JSON-schema validation, retries with exponential backoff, and automatic fallbacks prevent broken payloads from reaching the UI.

## Setup
1. **Clone & Python**: Use Python ≥ 3.11. Create a virtualenv if desired (`python -m venv .venv && source .venv/bin/activate`).
2. **Install dependencies**
   - With Poetry (recommended): `poetry install --no-root --with ingest`
   - With pip: `pip install -r build/requirements.txt`
3. **Configure secrets**
   - Provide an OpenAI key via environment variable or Streamlit secrets: `export OPENAI_API_KEY=...` or add `OPENAI_API_KEY` to `.streamlit/secrets.toml`.
   - Optional settings:
     - `OPENAI_API_BASE_URL=https://eu.api.openai.com/v1` to use the EU endpoint.
     - `USE_RESPONSES_API=1` (default) / `USE_CLASSIC_API=1` to select Responses vs. Chat.
     - `RESPONSES_ALLOW_TOOLS=0/1` to control tool payloads when allowlisted.
     - `VECTOR_STORE_ID` to enable OpenAI Vector Store retrieval.

## Running
- Start the Streamlit app: `poetry run streamlit run app.py` (or `streamlit run app.py` in your active environment).
- Keep the terminal session open; the wizard persists state in `st.session_state`.
- Use the Quick/Precise toggle in the onboarding/settings area to switch model routing. The admin/debug panel (when enabled) also exposes bilingual switches for Responses vs. Chat.

## Usage at a glance
1. Upload a PDF, paste a URL, or drop raw text on **Onboarding**. The app heuristically extracts emails, phones, and locations before calling the LLM.
2. Step through the wizard, reviewing AI-prefilled fields and inline follow-ups. Missing critical fields show bilingual banners.
3. On **Summary**, download structured JSON/Markdown, generate Boolean searches, or open the job-ad and interview-guide tabs. Exports reuse the stored profile, so edits stay in sync.

## Troubleshooting & FAQ
- **AI output is invalid JSON**: Retries and schema repairs run automatically. If the UI still shows empty sections, switch to **Precise/Genau** mode or toggle `USE_CLASSIC_API=1` to route through Chat completions.
- **OpenAI errors or rate limits**: Requests back off with exponential retries. If errors persist, lower traffic, try Quick mode, or pause before re-running the step. The debug panel shows which backend is active.
- **Responses stream returned nothing**: The client replays the request without streaming and then falls back to Chat; if the final `response.completed` event never arrives, a warning is logged and the prompt is retried via Chat completions. You can manually force Chat via `USE_CLASSIC_API` for the current session.
- **Use the EU endpoint**: Set `OPENAI_API_BASE_URL=https://eu.api.openai.com/v1` in your environment or Streamlit secrets.
- **Language support**: Extraction is optimised for full job descriptions in German or English; other languages may yield incomplete fields.

## Contributing
New contributors should:
- Follow PEP 8 and include type hints in all Python code.
- Run quality gates before opening a PR: `ruff format && ruff check`, `mypy --config-file pyproject.toml`, and `pytest -q` (or `-m "not integration"`).
- Work on feature branches named `feat/<short-description>` and open PRs against `dev` (no direct merges to `main`). Every PR should include release notes and Changelog updates.
- Read `docs/DEV_GUIDE.md` for details on adding wizard steps, follow-up questions, and schema propagation. See `CONTRIBUTING.md` for a concise checklist.
