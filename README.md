# Cognitive Staffing

Cognitive Staffing is a Streamlit wizard that converts unstructured job ads (PDFs, URLs, or pasted text) into a structured hiring profile and recruiter-ready outputs. It pairs rule-based ingest with OpenAI-powered extraction to prefill company, role, process, and compensation details, then guides users through eight bilingual steps to review, enrich, and export the results.

## Features
- **Eight-step wizard**: Onboarding → Company → Team & Structure → Role & Tasks → Skills & Requirements → Compensation → Hiring Process → Summary. Each step shows bilingual intros, validations, and inline follow-ups.
- **AI extraction & enrichment**: Ingest heuristics plus OpenAI Responses API map job ads into the NeedAnalysisProfile schema, highlight missing fields, and surface focused follow-up questions.
- **Interactive ChatKit assistant**: Missing critical fields open a bilingual ChatKit helper that asks concise follow-ups inside each step and writes the responses directly into the NeedAnalysisProfile.
- **Team composition advisor**: In the Team & Structure step, a bilingual AI copilot suggests realistic reporting lines and typical direct-report counts based on the role and company size, with one-click apply actions. (DE: Im Schritt „Team & Kontext“ schlägt ein zweisprachiger KI-Co-Pilot passende Berichtslinien und übliche Teamgrößen je nach Rolle und Unternehmensgröße vor; Vorschläge lassen sich per Klick übernehmen.)
- **Multilingual section detection**: German and English headings such as "Ihre Aufgaben"/"Your Tasks" or "Ihr Profil"/"Your Profile" are recognised so responsibilities and requirements land in the right fields (DE: Deutsche und englische Abschnittsüberschriften wie „Ihre Aufgaben“/„Your Tasks" bzw. „Ihr Profil“/„Your Profile“ werden erkannt, damit Aufgaben und Anforderungen korrekt zugeordnet werden.).
- **Benefits & perks capture**: Benefit sections like "Benefits", "Wir bieten", or "Unser Angebot" are pulled into compensation.benefits so offers show up in summaries and exports (DE: Benefit-Abschnitte wie „Benefits“, „Wir bieten“ oder „Unser Angebot“ werden in compensation.benefits übernommen, damit Angebote in Zusammenfassungen und Exporten erscheinen.).
- **Hiring process extraction**: Interview or application steps called out as "Hiring process", "Interview process", "Bewerbungsprozess" etc. are captured into the process section so reviewers see known stages immediately (DE: Als „Hiring/Interview/Bewerbungsprozess“ beschriebene Abläufe werden im Prozess-Abschnitt übernommen, damit bekannte Schritte direkt sichtbar sind.).
- **AI hiring process planner**: A bilingual assistant in the Hiring Process step suggests a seniority-aware stage sequence (screening, technical, panel, leadership), lets you reorder or trim steps, and saves the confirmed list into `process.hiring_process` (DE: Ein zweisprachiger Assistent im Prozess-Schritt schlägt je nach Seniorität passende Stufen vor, erlaubt Umordnen oder Entfernen und speichert die finale Liste in `process.hiring_process`).
- **Company intro parsing**: About-us blurbs or opening paragraphs are summarised into `company.description` and the main sector is captured in `company.industry` so recruiters get instant context (DE: „Über uns“-Abschnitte werden kurz zusammengefasst und die Branche in `company.industry` eingetragen, damit der Kontext direkt ersichtlich ist.).
- **Schema-safe defaults**: Required NeedAnalysis fields are auto-populated with neutral placeholders so summaries and follow-ups always render. (DE: Pflichtfelder des NeedAnalysis-Schemas werden mit neutralen Platzhaltern aufgefüllt, damit Zusammenfassungen und Follow-ups stets angezeigt werden.)
- **Quick vs. Precise modes**: The in-app toggle routes **Quick/Schnell** flows to `gpt-4.1-mini` (fast, low reasoning effort) and **Precise/Genau** flows to the reasoning tier (`o4-mini` for medium effort or `o3` for high effort) via `REASONING_EFFORT` and routing fallbacks. Cache keys are mode-aware so switching modes refreshes results.
- **Responses vs. Chat API**: By default `USE_RESPONSES_API=1` keeps structured calls on the OpenAI Responses API; set `USE_CLASSIC_API=1` (or clear `USE_RESPONSES_API`) to force the legacy Chat Completions fallback. When Responses returns empty streams, the client cascades to Chat and then curated static suggestions.
- **Boolean search & exports**: Build Boolean strings, job ads, and interview guides directly from the stored profile. Summary tabs separate **Role tasks & search**, **Job ad**, and **Interview guide** for easy review.
- **ESCO integration**: Optional ESCO skill lookups (read-only GET) enrich extracted skills with cached taxonomy mappings.
- **Structured skill buckets**: Extracted requirements are auto-split and classified into hard/soft skills, tools & technologies, languages, and certifications using ESCO metadata plus bilingual heuristics (DE: Extrahierte Anforderungen werden automatisch aufgeteilt und als Hard/Soft Skills, Tools & Technologien, Sprachen und Zertifizierungen einsortiert – gestützt auf ESCO-Metadaten und zweisprachige Heuristiken.).
- **Retried, structured outputs**: Strict JSON-schema validation, retries with exponential backoff, and automatic fallbacks prevent broken payloads from reaching the UI.
- **UI polish**: The Employment step spaces the Work schedule dropdown on its own row so it stays visually separate from nearby toggles/fields, and hidden inputs now carry accessible labels to silence Streamlit empty-label warnings (DE: Das Arbeitszeitmodell-Dropdown im Beschäftigungs-Schritt hat nun eine eigene, luftige Zeile und kollidiert nicht mehr mit benachbarten Eingaben; ausgeblendete Eingabefelder besitzen nun zugängliche Beschriftungen, damit Streamlit keine Warnungen zu leeren Labels mehr ausgibt).

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
     - `LIGHTWEIGHT_MODEL`, `MEDIUM_REASONING_MODEL`, or `HIGH_REASONING_MODEL` to override the quick/medium/high routing tiers.
     - `VECTOR_STORE_ID` to enable OpenAI Vector Store retrieval.
     - `CHATKIT_ENABLED=1` to surface the ChatKit follow-up assistant (default). Set `CHATKIT_DOMAIN_KEY` and `CHATKIT_WORKFLOW_ID` when embedding the hosted widget on your allow-listed Streamlit domain.

## Running
- Start the Streamlit app: `poetry run streamlit run app.py` (or `streamlit run app.py` in your active environment).
- Keep the terminal session open; the wizard persists state in `st.session_state`.
- Use the Quick/Precise toggle in the onboarding/settings area to switch model routing. The admin/debug panel (when enabled) also exposes bilingual switches for Responses vs. Chat.

## Usage at a glance
1. Upload a PDF, paste a URL, or drop raw text on **Onboarding**. The app heuristically extracts emails, phones, and locations before calling the LLM.
2. Step through the wizard, reviewing AI-prefilled fields and inline follow-ups. Missing critical fields launch the bilingual ChatKit assistant, which captures answers and mirrors them into the profile instantly.
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
- Keep `schema/need_analysis.schema.json` in sync with `NeedAnalysisProfile` via `PYTHONPATH=. python cli/generate_schema.py` whenever schema fields change (CS_SCHEMA_PROPAGATE).
- Load the NeedAnalysis JSON schema via `core.schema_registry.load_need_analysis_schema()` rather than reading files directly so prompts, repairs, and CLIs share the same source of truth.
- Work on feature branches named `feat/<short-description>` and open PRs against `dev` (no direct merges to `main`). Every PR should include release notes and Changelog updates.
- Keep wizard step UIs in `wizard/steps/` modules (e.g., `company_step.py`, `team_step.py`) and let `wizard/flow.py` focus on routing/orchestration. (DE: Wizard-Schritte liegen in `wizard/steps/`; `wizard/flow.py` bündelt nur das Routing.)
- Route LLM orchestration through reusable pipeline helpers (e.g., `pipelines.need_analysis.extract_need_analysis_profile`) so Streamlit rendering stays UI-only (DE: LLM-Orchestrierung über wiederverwendbare Pipeline-Helfer wie `pipelines.need_analysis.extract_need_analysis_profile` führen, damit die Streamlit-Logik UI-only bleibt.).
- Read `docs/DEV_GUIDE.md` for details on adding wizard steps, follow-up questions, and schema propagation. See `CONTRIBUTING.md` for a concise checklist.
