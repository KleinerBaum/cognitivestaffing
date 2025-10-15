# Cognitive Staffing

**Cognitive Staffing** automates the extraction and enrichment of vacancy profiles from PDFs, URLs, or pasted text. It turns unstructured job ads into structured JSON, highlights missing data, and orchestrates multiple AI agents to draft follow-up questions, job ads, interview guides, and Boolean searches. By default all LLM calls run through the OpenAI **Responses API** (with the `gpt-5` family) so we can enforce structured outputs, stream long generations, and fall back gracefully when rate limits occur. If needed, set the `USE_CLASSIC_API` environment variable to route every call through the Chat Completions API instead.

![App Screenshot](images/app_screenshot.png)

## Feature Highlights
- **Structured extraction:** JSON schemas and Pydantic validation keep 20+ vacancy fields aligned with `NeedAnalysisProfile`. Locked fields such as **job_title** or **company** are auto-filled when rule matches fire and stay protected until you unlock them.
- **Interactive follow-ups:** A Follow-up Question Generator agent produces prioritized follow-up questions with suggestion chips. When ESCO metadata is available the assistant injects normalized essential skills into the prompts, and the auto re-ask loop keeps rerunning critical prompts until every must-have field is answered.
- **ESCO integration:** When enabled, the ESCO enricher normalizes job titles, proposes essential skills, and flags missing competencies directly in the UI.
- **AI-assisted suggestions:** Dedicated helpers surface skills, benefits, responsibilities, boolean strings, interview guides, and polished job ads. Responses stream live by default so the UI stays responsive during longer generations.
- **Analysis helpers / Analyse-Helfer:**
  **EN:** Deterministic tools expose salary benchmarks, currency conversion with cached FX rates, and ISO date normalisation so the assistant can ground reasoning steps without extra API calls.
  **DE:** Deterministische Helfer liefern Gehaltsbenchmarks, Währungsumrechnung mit zwischengespeicherten FX-Kursen und ISO-Datumsnormalisierung, damit der Assistent ohne zusätzliche APIs fundiert begründen kann.
- **Vector-store enrichment:** Provide `VECTOR_STORE_ID` to let the RAG agent retrieve supporting snippets via OpenAI **file_search**, seeding better suggestions when the uploaded job ad is sparse.
- **Multi-model routing:** The router sends high-complexity tasks to `gpt-5.1-mini` (the official GPT-5 mini endpoint) and lightweight lookups to `gpt-5.1-nano` (GPT-5 nano), keeping costs predictable without sacrificing quality.
- **Gap analysis workspace / Gap-Analyse-Arbeitsbereich:**
  **EN:** Launch the **Gap analysis** view to combine ESCO metadata, retrieved snippets, and vacancy text into an executive-ready report that highlights missing information and next steps.
  **DE:** Öffne die Ansicht **Gap-Analyse**, um ESCO-Metadaten, abgerufene Snippets und Ausschreibungstext zu einem Management-tauglichen Bericht mit offenen Punkten und nächsten Schritten zu verbinden.
- **Deliberate UX:** Wizard steps expose inline help that explains why fields are locked or why suggestions may be missing, a sidebar tracks progress, and branded dark/light themes align with Cognitive Staffing colors.

## Model Routing & Cost Controls / Modellrouting & Kostensteuerung

- **Content cost router / Kostenrouter für Inhalte**  
  **EN:** Each request runs through a prompt cost router that inspects token length and hard-to-translate compounds before selecting the cheapest suitable GPT-5 tier. Short, simple prompts stay on `gpt-5.1-nano` (GPT-5 nano), while complex or multilingual payloads automatically escalate to `gpt-5.1-mini` (GPT-5 mini) for higher quality without manual tuning.
  **DE:** Jede Anfrage durchläuft einen Kostenrouter, der Tokenlänge und schwer übersetzbare Komposita prüft, bevor das günstigste passende GPT-5-Modell gewählt wird. Kurze, einfache Prompts bleiben auf `gpt-5.1-nano` (GPT-5 nano), komplexe oder mehrsprachige Eingaben wechseln automatisch auf `gpt-5.1-mini` (GPT-5 mini), um Qualität ohne manuelles Feintuning sicherzustellen.
- **Fallback chain (GPT-4/GPT-3.5) / Fallback-Kette (GPT-4/GPT-3.5)**  
  **EN:** If an API call reports that a GPT-5 model is overloaded or deprecated, the platform marks it as unavailable and retries with `gpt-4o`, then `gpt-3.5-turbo`. This automatic degradation keeps the wizard responsive during outages while still logging which tier delivered the final response.  
  **DE:** Meldet die API, dass ein GPT-5-Modell überlastet oder abgekündigt ist, markiert die Plattform es als nicht verfügbar und versucht es erneut mit `gpt-4o`, danach mit `gpt-3.5-turbo`. Diese automatische Abstufung hält den Wizard auch bei Störungen reaktionsfähig und protokolliert, welches Modell die endgültige Antwort geliefert hat.
- **Model override toggle / Modell-Override-Umschalter**  
  **EN:** Open the sidebar settings and use the **Base model** select box to force a specific tier. Choosing “Auto” clears the override so routing and fallbacks can operate normally; selecting “Force GPT-5 mini (`gpt-5.1-mini`)” or “Force GPT-5 nano (`gpt-5.1-nano`)” pins every request to that engine until you switch back.  
  **DE:** Öffne die Einstellungen in der Seitenleiste und nutze das Auswahlfeld **Basismodell**, um einen bestimmten Modell-Tier zu erzwingen. Mit „Automatisch“ wird der Override aufgehoben, sodass Routing und Fallbacks normal greifen; „GPT-5 mini (`gpt-5.1-mini`) erzwingen“ bzw. „GPT-5 nano (`gpt-5.1-nano`) erzwingen“ fixiert jede Anfrage auf diese Engine, bis du wieder zurückschaltest.

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
> **Note / Hinweis:** We pin `streamlit-sortables` to version 0.3.1 because it is the latest release published to PyPI; the wizard drag-and-drop UI remains fully compatible with this build.
> **Hinweis:** Wir fixieren `streamlit-sortables` auf Version 0.3.1, da dies die jüngste auf PyPI verfügbare Veröffentlichung ist; die Drag-and-Drop-Oberfläche des Wizards bleibt damit vollständig kompatibel.

> **Dependency policy / Abhängigkeitsrichtlinie:**
> **EN:** Dependency management is now unified in `requirements.txt` for both runtime and developer tooling. Remove legacy `pip install -e .` flows—the lint/type-check configuration now lives in `pyproject.toml`.
> **DE:** Die Abhängigkeitsverwaltung erfolgt vollständig über `requirements.txt` – sowohl für Laufzeit als auch Entwickler-Tools. Bitte ältere Workflows mit `pip install -e .` nicht mehr verwenden; die Lint-/Typisierungsregeln stehen jetzt in `pyproject.toml`.

### 4. Provide OpenAI credentials
Set environment variables (or configure `.streamlit/secrets.toml` under the `openai` key):
```bash
export OPENAI_API_KEY="sk-..."
# Optional overrides
export OPENAI_BASE_URL="https://api.openai.com/v1"          # use https://eu.api.openai.com/v1 for EU residency
export OPENAI_MODEL="gpt-5.1-mini"                            # default model override (GPT-5 mini)
export OPENAI_REQUEST_TIMEOUT="120"                          # seconds; extend for long-running generations
export REASONING_EFFORT="medium"                             # minimal | low | medium | high
export VERBOSITY="medium"                                     # low | medium | high (Antwort-Detailgrad)
export VECTOR_STORE_ID="vs_XXXXXXXXXXXXXXXX"                 # enable RAG lookups (optional)
export OTEL_EXPORTER_OTLP_ENDPOINT="https://otel.example/v1/traces"  # optional tracing
export OTEL_SERVICE_NAME="cognitive-staffing"
export USE_CLASSIC_API="1"                                    # set to 1 to force Chat Completions (Responses bleibt Standard)
```
You can also add `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_REQUEST_TIMEOUT`, `VERBOSITY`, and `VECTOR_STORE_ID` to `st.secrets` if you prefer Streamlit's secret storage. When `OPENAI_BASE_URL` points to `https://eu.api.openai.com/v1`, all traffic stays within the EU region.

> **EN:** Leave `USE_CLASSIC_API` unset to keep the Responses client as the default. Set it to `1` if you need to fall back to the legacy Chat Completions API for compatibility.
> **DE:** Lass `USE_CLASSIC_API` leer, damit standardmäßig der Responses-Client genutzt wird. Setze den Wert auf `1`, wenn du aus Kompatibilitätsgründen auf die klassische Chat-Completions-API zurückfallen musst.

### 5. (Optional) Configure OCR & branding
- Set `OCR_BACKEND=none` to disable OCR (default). Provide `OCR_BACKEND=openai` to use OpenAI Vision for image/PDF parsing.
- Use the sidebar **⚙️ Einstellungen / Settings** section to switch between the built-in dark 🌙 and light ☀️ themes.
- Upload your company logo via the **Logo hochladen (optional) / Upload logo (optional)** control in the Company step.
> **EN:** Additional color tweaks require editing `styles/cognitive_needs.css` (dark) and `styles/cognitive_needs_light.css` (light); there is no in-app color picker.
> **DE:** Für weitere Farbänderungen musst du `styles/cognitive_needs.css` (Dark Theme) und `styles/cognitive_needs_light.css` (Light Theme) anpassen; ein Farb-Picker ist derzeit nicht vorhanden.

### 6. Launch the app
```bash
streamlit run app.py
```
Streamlit prints a local URL; open it in your browser to start the wizard.

### 7. Optional: Build a vector store for RAG / Optional: Vector-Store für RAG erstellen

**EN:** Use the helper CLI to re-embed an OpenAI vector store before enabling Retrieval-Augmented Generation. The command copies your existing store, upgrades embeddings to `text-embedding-3-large`, and prints the new identifier.

**DE:** Verwende das CLI-Hilfsprogramm, um vor der Aktivierung der Retrieval-Augmented-Generation einen OpenAI-Vector-Store neu einzubetten. Der Befehl dupliziert den bestehenden Store, aktualisiert die Embeddings auf `text-embedding-3-large` und gibt die neue Kennung aus.

```bash
python -m cli.rebuild_vector_store vs_existing_store_id
# Update VECTOR_STORE_ID with the printed target value
```

## Usage Guide
1. **Load a job ad:** Upload a PDF/DOCX/TXT file or paste a URL/text snippet. Extraction runs automatically, locking high-confidence fields.
2. **Review the overview:** The sidebar highlights which fields were rule-matched, inferred by AI, or still missing. Adjust the **Response verbosity** setting (Deutsch: *Antwort-Detailgrad*) to switch between concise and detailed AI explanations.
3. **Answer follow-ups:** The Follow-up Question Generator asks targeted questions. Enable *Auto follow-ups* to let the agent re-run until all critical gaps are closed.
4. **Enrich requirements:** Accept AI suggestions for skills, benefits, salary ranges, and responsibilities. Tooltips explain why suggestions might be empty (e.g., locked fields, missing context, or disabled RAG).
5. **Generate deliverables:** Use the summary step to stream job ads, interview guides, and Boolean search strings. Each generation shows usage metrics and supports instant regeneration with new instructions.
6. **Export:** Download the structured vacancy JSON, job ad Markdown, and interview guide directly from the summary workspace.

## RAG Quickstart / RAG-Schnellstart

**Step 1 / Schritt 1:**
  **EN:** Run `python -m cli.rebuild_vector_store <source_store_id>` (or create a fresh store in the OpenAI dashboard) and place the returned ID in the `VECTOR_STORE_ID` environment variable or `st.secrets`.
  **DE:** Führe `python -m cli.rebuild_vector_store <source_store_id>` aus (oder erstelle im OpenAI-Dashboard einen neuen Store) und hinterlege die ausgegebene ID in der Umgebungsvariable `VECTOR_STORE_ID` oder in `st.secrets`.

**Step 2 / Schritt 2:**
  **EN:** Upload a job ad and open the **Gap analysis** or **Follow-up questions** panel. The RAG pipeline (`llm/rag_pipeline.py`) adds the best-matching snippets to the agent prompt so that follow-up suggestions contain grounded evidence links.
  **DE:** Lade eine Stellenanzeige hoch und öffne die Ansicht **Gap-Analyse** oder das Panel **Nachfragen**. Die RAG-Pipeline (`llm/rag_pipeline.py`) ergänzt die Agenten-Prompts um passende Ausschnitte, sodass Nachfragen begründete Hinweise enthalten.

**Step 3 / Schritt 3:**
  **EN:** Use the inline “Refresh suggestions” button to trigger another retrieval round when you change key fields. Missing vector-store configuration raises a localized hint instead of blocking the wizard.
  **DE:** Nutze den Inline-Button „Vorschläge aktualisieren“, um nach einer Feldänderung eine neue Retrieval-Runde zu starten. Fehlt die Vector-Store-Konfiguration, erscheint ein lokalisierter Hinweis, ohne den Wizard zu blockieren.

## Troubleshooting & Tips
- **Missing suggestions?** Ensure the job title is set, unlock the field if it’s frozen by rule logic, and verify that `OPENAI_API_KEY` and (optionally) `VECTOR_STORE_ID` are configured.
- **EU data residency:** Point `OPENAI_BASE_URL` to `https://eu.api.openai.com/v1`. The selected LLM client automatically uses the base URL for all agents.
- **Rate limits:** The `llm` utilities automatically apply exponential backoff and display user-friendly error banners with retry guidance.
- **Telemetry:** If OpenTelemetry variables are set, traces include model name, latency, token usage, and retry metadata for each agent.

## Further Reading
- [AGENTS.md](AGENTS.md) for an overview of every autonomous agent (Follow-up generator, ESCO enricher, RAG assistant, compliance plans, etc.).
- [docs/](docs/) for schema references, JSON pipelines, and changelogs.

Happy hiring!
