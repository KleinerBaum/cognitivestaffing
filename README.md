# Cognitive Staffing

**Cognitive Staffing** automates the extraction and enrichment of vacancy profiles from PDFs, URLs, or pasted text. It turns unstructured job ads into structured JSON, highlights missing data, and orchestrates multiple AI agents to draft follow-up questions, job ads, interview guides, and Boolean searches. All LLM calls run through the OpenAI **Responses API** (with the `gpt-5` family) so we can enforce structured outputs, stream long generations, and fall back gracefully when rate limits occur.

![App Screenshot](images/app_screenshot.png)

## Feature Highlights
- **Structured extraction:** JSON schemas and Pydantic validation keep 20+ vacancy fields aligned with `NeedAnalysisProfile`. Locked fields such as **job_title** or **company** are auto-filled when rule matches fire and stay protected until you unlock them.
- **Interactive follow-ups:** A Follow-up Question Generator agent produces prioritized follow-up questions with suggestion chips. The auto re-ask loop keeps rerunning critical prompts until every must-have field is answered.
- **ESCO integration:** When enabled, the ESCO enricher normalizes job titles, proposes essential skills, and flags missing competencies directly in the UI.
- **AI-assisted suggestions:** Dedicated helpers surface skills, benefits, responsibilities, boolean strings, interview guides, and polished job ads. Responses stream live so the UI stays responsive during longer generations.
- **Vector-store enrichment:** Provide `VECTOR_STORE_ID` to let the RAG agent retrieve supporting snippets via OpenAI **file_search**, seeding better suggestions when the uploaded job ad is sparse.
- **Multi-model routing:** The router sends high-complexity tasks to `gpt-5-mini` and lightweight lookups to `gpt-5-nano`, keeping costs predictable without sacrificing quality.
- **Deliberate UX:** Wizard steps expose inline help that explains why fields are locked or why suggestions may be missing, a sidebar tracks progress, and branded dark/light themes align with Cognitive Staffing colors.

## Model Routing & Cost Controls / Modellrouting & Kostensteuerung

- **Content cost router / Kostenrouter für Inhalte**  
  **EN:** Each request runs through a prompt cost router that inspects token length and hard-to-translate compounds before selecting the cheapest suitable GPT-5 tier. Short, simple prompts stay on `gpt-5-nano`, while complex or multilingual payloads automatically escalate to `gpt-5-mini` for higher quality without manual tuning.  
  **DE:** Jede Anfrage durchläuft einen Kostenrouter, der Tokenlänge und schwer übersetzbare Komposita prüft, bevor das günstigste passende GPT-5-Modell gewählt wird. Kurze, einfache Prompts bleiben auf `gpt-5-nano`, komplexe oder mehrsprachige Eingaben wechseln automatisch auf `gpt-5-mini`, um Qualität ohne manuelles Feintuning sicherzustellen.
- **Fallback chain (GPT-4/GPT-3.5) / Fallback-Kette (GPT-4/GPT-3.5)**  
  **EN:** If an API call reports that a GPT-5 model is overloaded or deprecated, the platform marks it as unavailable and retries with `gpt-4o`, then `gpt-3.5-turbo`. This automatic degradation keeps the wizard responsive during outages while still logging which tier delivered the final response.  
  **DE:** Meldet die API, dass ein GPT-5-Modell überlastet oder abgekündigt ist, markiert die Plattform es als nicht verfügbar und versucht es erneut mit `gpt-4o`, danach mit `gpt-3.5-turbo`. Diese automatische Abstufung hält den Wizard auch bei Störungen reaktionsfähig und protokolliert, welches Modell die endgültige Antwort geliefert hat.
- **Model override toggle / Modell-Override-Umschalter**  
  **EN:** Open the sidebar settings and use the **Base model** select box to force a specific tier. Choosing “Auto” clears the override so routing and fallbacks can operate normally; selecting “Force GPT-5 mini” or “Force GPT-5 nano” pins every request to that engine until you switch back.  
  **DE:** Öffne die Einstellungen in der Seitenleiste und nutze das Auswahlfeld **Basismodell**, um einen bestimmten Modell-Tier zu erzwingen. Mit „Automatisch“ wird der Override aufgehoben, sodass Routing und Fallbacks normal greifen; „GPT-5 mini erzwingen“ bzw. „GPT-5 nano erzwingen“ fixiert jede Anfrage auf diese Engine, bis du wieder zurückschaltest.

## Architecture at a Glance
The Streamlit app lives in `app.py` and delegates to the domain modules under `core/`, `wizard.py`, and `components/`. LLM utilities in `llm/` implement a unified `ChatCallResult` wrapper with retry, tool execution, and JSON-mode enforcement. Agents (documented in [AGENTS.md](AGENTS.md)) operate on shared state inside `st.session_state`, enabling features like auto follow-ups, ESCO lookups, and streaming document generation.

```
streamlit app.py → wizard (UI) → core/question_logic → llm responses
                             ↘ ingest/ (PDF, HTML, OCR)
                              ↘ integrations/ (ESCO, vector store)
```

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/KleinerBaum/cognitivestaffing.git
cd cognitivestaffing
```

### 2. Create a virtual environment
```bash
python3.11 -m venv .venv  # Python 3.11 or 3.12
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```
The requirements list includes Streamlit, OpenAI, Pydantic, jsonschema, vector retrieval helpers, and optional observability (`opentelemetry-*`). The German spaCy model (`de-core-news-sm`) is installed automatically for rule-based location fallback.

### 4. Provide OpenAI credentials
Set environment variables (or configure `.streamlit/secrets.toml` under the `openai` key):
```bash
export OPENAI_API_KEY="sk-..."
# Optional overrides
export OPENAI_BASE_URL="https://api.openai.com/v1"          # use https://eu.api.openai.com/v1 for EU residency
export OPENAI_MODEL="gpt-5-mini"                             # default model override
export REASONING_EFFORT="medium"                             # low | medium | high
export VECTOR_STORE_ID="vs_XXXXXXXXXXXXXXXX"                 # enable RAG lookups (optional)
export OTEL_EXPORTER_OTLP_ENDPOINT="https://otel.example/v1/traces"  # optional tracing
export OTEL_SERVICE_NAME="cognitive-staffing"
```
You can also add `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, and `VECTOR_STORE_ID` to `st.secrets` if you prefer Streamlit's secret storage. When `OPENAI_BASE_URL` points to `https://eu.api.openai.com/v1`, all traffic stays within the EU region.

### 5. (Optional) Configure OCR & branding
- Set `OCR_BACKEND=none` to disable OCR (default). Provide `OCR_BACKEND=openai` to use OpenAI Vision for image/PDF parsing.
- Upload your own logo and colors via the UI branding controls, or adjust the themes in `styles/`.

### 6. Launch the app
```bash
streamlit run app.py
```
Streamlit prints a local URL; open it in your browser to start the wizard.

## Usage Guide
1. **Load a job ad:** Upload a PDF/DOCX/TXT file or paste a URL/text snippet. Extraction runs automatically, locking high-confidence fields.
2. **Review the overview:** The sidebar highlights which fields were rule-matched, inferred by AI, or still missing.
3. **Answer follow-ups:** The Follow-up Question Generator asks targeted questions. Enable *Auto follow-ups* to let the agent re-run until all critical gaps are closed.
4. **Enrich requirements:** Accept AI suggestions for skills, benefits, salary ranges, and responsibilities. Tooltips explain why suggestions might be empty (e.g., locked fields, missing context, or disabled RAG).
5. **Generate deliverables:** Use the summary step to stream job ads, interview guides, and Boolean search strings. Each generation shows usage metrics and supports instant regeneration with new instructions.
6. **Export:** Download the structured vacancy JSON, job ad Markdown, and interview guide directly from the summary workspace.

## Troubleshooting & Tips
- **Missing suggestions?** Ensure the job title is set, unlock the field if it’s frozen by rule logic, and verify that `OPENAI_API_KEY` and (optionally) `VECTOR_STORE_ID` are configured.
- **EU data residency:** Point `OPENAI_BASE_URL` to `https://eu.api.openai.com/v1`. The Responses client automatically uses the base URL for all agents.
- **Rate limits:** The `llm` utilities automatically apply exponential backoff and display user-friendly error banners with retry guidance.
- **Telemetry:** If OpenTelemetry variables are set, traces include model name, latency, token usage, and retry metadata for each agent.

## Further Reading
- [AGENTS.md](AGENTS.md) for an overview of every autonomous agent (Follow-up generator, ESCO enricher, RAG assistant, compliance plans, etc.).
- [docs/](docs/) for schema references, JSON pipelines, and changelogs.

Happy hiring!
