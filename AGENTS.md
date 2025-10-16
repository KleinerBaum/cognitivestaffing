# Autonomous Agents in Cognitive Staffing / Autonome Agenten in Cognitive Staffing

**EN:** This guide summarises every autonomous or semi-autonomous agent, tool, and supporting configuration that powers Cognitive Staffing. Use it to understand data flow, required credentials, and extension points.

**DE:** Dieses Dokument beschreibt alle autonomen bzw. halb-autonomen Agenten, Tools und Konfigurationen von Cognitive Staffing. Es erklärt Datenflüsse, benötigte Zugangsdaten und Ansatzpunkte für Erweiterungen.

## Configuration / Konfiguration

- `OPENAI_API_KEY`
  - **EN:** Mandatory for every LLM request (Responses API by default). Can be provided via environment variables or `st.secrets["openai"]`.
  - **DE:** Pflichtwert für alle LLM-Anfragen (standardmäßig Responses API). Entweder als Umgebungsvariable oder in `st.secrets["openai"]` hinterlegen.
- `OPENAI_BASE_URL`
  - **EN:** Optional base URL override. Set to `https://eu.api.openai.com/v1` for EU data residency.
  - **DE:** Optionale Basis-URL. Für EU-Datenresidenz `https://eu.api.openai.com/v1` setzen.
- `OPENAI_MODEL`
  - **EN:** Optional global default. Routing now balances `gpt-4o` (full) and `gpt-4o-mini` (cost-optimised) per task, while manual overrides can force GPT-5 tiers.
  - **DE:** Optionaler globaler Standard. Das Routing balanciert nun je nach Aufgabe zwischen `gpt-4o` (voll) und `gpt-4o-mini` (kostenoptimiert); manuelle Overrides können weiterhin GPT-5-Tiers erzwingen.
- `OPENAI_REQUEST_TIMEOUT`
  - **EN:** Timeout in seconds for Responses requests (default: 120s). Increase for long-running generations.
  - **DE:** Timeout in Sekunden für Responses-Anfragen (Standard: 120s). Für lange Generierungen erhöhen.
- `REASONING_EFFORT`
  - **EN:** Controls reasoning depth (`minimal`, `low`, `medium`, `high`) consumed by the router.
  - **DE:** Steuert die Reasoning-Tiefe (`minimal`, `low`, `medium`, `high`) für das Routing.
- `VERBOSITY`
  - **EN:** Configures UI explanation level (`low`, `medium`, `high`).
  - **DE:** Legt den Erklärungsgrad in der UI fest (`low`, `medium`, `high`).
- `VECTOR_STORE_ID`
  - **EN:** Optional OpenAI Vector Store identifier for Retrieval-Augmented Generation (`file_search` tool). When unset, RAG gracefully disables itself and surfaces localized hints in the UI.
  - **DE:** Optionale OpenAI-Vector-Store-ID für Retrieval-Augmented-Generation (`file_search` Tool). Ohne Wert deaktiviert sich RAG selbst und zeigt lokalisierte Hinweise in der UI.
- `VACAYSER_OFFLINE`
  - **EN:** Set to `1` to use the bundled ESCO cache instead of the public API.
  - **DE:** Auf `1` setzen, um den mitgelieferten ESCO-Cache statt der öffentlichen API zu verwenden.
- `USE_CLASSIC_API`
  - **EN:** When set to `1`, forces the legacy Chat Completions API; leave unset to use Responses.
  - **DE:** Bei Wert `1` wird die klassische Chat-Completions-API erzwungen; ohne Wert bleibt Responses aktiv.
- `OCR_BACKEND`
  - **EN:** Choose `none` (default) to disable OCR or `openai` to enable Vision OCR for PDFs/images.
  - **DE:** Mit `none` (Standard) OCR deaktivieren oder `openai` für Vision-OCR bei PDFs/Bildern wählen.
- OpenTelemetry (`OTEL_*`)
  - **EN:** Configure tracing via variables such as `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`, `OTEL_TRACES_SAMPLER`, and companions. See `docs/telemetry.md` for details.
  - **DE:** Tracing über Variablen wie `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME`, `OTEL_TRACES_SAMPLER` usw. konfigurieren. Details in `docs/telemetry.md`.

> **CLI support / CLI-Unterstützung:**
> - **EN:** `python -m cli.rebuild_vector_store <source_store_id>` clones an existing OpenAI vector store and upgrades embeddings to `text-embedding-3-large` for RAG agents. Update `VECTOR_STORE_ID` with the printed target.
> - **DE:** `python -m cli.rebuild_vector_store <source_store_id>` klont einen bestehenden OpenAI-Vector-Store, aktualisiert die Embeddings auf `text-embedding-3-large` für die RAG-Agenten und gibt die neue ID aus. Diese in `VECTOR_STORE_ID` hinterlegen.

## Core Agents / Kernagenten

### 1. Follow-up Question Generator (FQG) / Nachfragen-Generator
- **Purpose / Zweck:**
  - **EN:** Converts partially filled vacancy JSON into prioritised follow-up questions (`critical`, `normal`, `optional`) including suggestion chips.
  - **DE:** Verwandelt teilweise ausgefüllte Stellenprofile in priorisierte Nachfragen (`critical`, `normal`, `optional`) inklusive Vorschlags-Chips.
- **Inputs / Eingaben:**
  - **EN:** Current vacancy profile (`extracted`), locale (`lang`), optional ESCO metadata, optional RAG suggestions.
  - **DE:** Aktuelles Stellenprofil (`extracted`), Sprache (`lang`), optionale ESCO-Metadaten, optionale RAG-Vorschläge.
- **Outputs / Ausgaben:**
  - **EN:** JSON payload `{ "questions": [ { field, question, priority, suggestions } ] }` enforced via Responses JSON schema.
  - **DE:** JSON-Nutzlast `{ "questions": [ { field, question, priority, suggestions } ] }`, abgesichert über die Responses-JSON-Schema-Funktion.
- **Model & tools / Modell & Tools:**
  - **EN:** `gpt-4o` via `responses.create`. Automatically activates `file_search` when `VECTOR_STORE_ID` is configured.
  - **DE:** `gpt-4o` über `responses.create`. Aktiviert `file_search` automatisch, sobald `VECTOR_STORE_ID` gesetzt ist.
- **Lifecycle / Ausführung:**
  - **EN:** Runs after extraction and whenever the user replays follow-ups (manual rerun or Auto re-ask loop).
  - **DE:** Läuft nach der Extraktion und bei jedem erneuten Anstoßen der Nachfragen (manuell oder durch den Auto-Reask-Loop).

### 2. ESCO Enricher / ESCO-Anreicherer
- **Purpose / Zweck:**
  - **EN:** Normalises job titles, fetches essential ESCO skills, and highlights gaps for UI indicators.
  - **DE:** Normalisiert Jobtitel, lädt essentielle ESCO-Kompetenzen und hebt Lücken für UI-Indikatoren hervor.
- **Inputs / Eingaben:** `job_title`, `lang`, current requirements / aktueller Requirements-Block.
- **Outputs / Ausgaben:**
  - **EN:** Occupation metadata (`preferredLabel`, group, URI), `essential_skills`, `missing_esco_skills`, and label mappings.
  - **DE:** Berufsmetadaten (`preferredLabel`, Gruppe, URI), `essential_skills`, `missing_esco_skills` sowie Label-Mappings.
- **Model & tools / Modell & Tools:**
  - **EN:** ESCO REST API (no LLM cost). Falls back to offline cache when `VACAYSER_OFFLINE=1`.
  - **DE:** ESCO-REST-API (keine LLM-Kosten). Fällt bei `VACAYSER_OFFLINE=1` auf den Offline-Cache zurück.
- **Lifecycle / Ausführung:**
  - **EN/DE:** Triggered during extraction, on job-title changes, and while generating skill suggestions.

### 3. RAG Completion Agent / RAG-Vervollständigungsagent
- **Purpose / Zweck:**
  - **EN:** Retrieves vector-store snippets to pre-fill missing fields or strengthen answer suggestions.
  - **DE:** Holt Vector-Store-Snippets, um fehlende Felder vorzufüllen oder Antwortvorschläge zu verbessern.
- **Inputs / Eingaben:** Vacancy context (title, seniority, existing JSON) and missing-field list / Kontext der Stelle (Titel, Seniorität, bestehendes JSON) plus Liste fehlender Felder.
- **Outputs / Ausgaben:**
  - **EN:** `rag_suggestions` mapping fields to candidate values and rationales.
  - **DE:** `rag_suggestions`, die Felder auf Kandidatenwerte und Begründungen abbilden.
- **Model & tools / Modell & Tools:**
  - **EN/DE:** `gpt-4o` with the `file_search` tool against the configured vector store.
- **Lifecycle / Ausführung:**
  - **EN:** Runs before the FQG to seed suggestion chips and when users click “Refresh suggestions”.
  - **DE:** Läuft vor dem Nachfragen-Agenten zur Initialbefüllung der Chips und beim Klick auf „Vorschläge aktualisieren“.

### 4. Company Intel Agent / Unternehmens-Insights-Agent
- **Purpose / Zweck:**
  - **EN:** Extracts company name, location, mission, and culture from fetched website content.
  - **DE:** Extrahiert Unternehmensname, Standort, Mission und Kultur aus geladenen Webseiteninhalten.
- **Inputs / Eingaben:** Company URL + fetched HTML/PDF text / Unternehmens-URL plus geladener HTML/PDF-Text.
- **Outputs / Ausgaben:** `{ company_name, location, company_mission, company_culture }` (EN/DE identisch).
- **Model & tools / Modell & Tools:** `gpt-3.5-turbo` with structured extraction prompts / strukturierte Extraktion.
- **Lifecycle / Ausführung:** On “Fetch from website” or when a URL is supplied / Beim Klick auf „Von Website laden“ oder beim Setzen einer URL.

### 5. Suggestion Helpers / Vorschlags-Helfer
- **Purpose / Zweck:**
  - **EN:** Task, skill, benefit, boolean-query, interview-guide, and job-ad helpers enrich vacancy data with focused outputs.
  - **DE:** Aufgaben-, Skill-, Benefit-, Boolean-Query-, Interviewleitfaden- und Job-Ad-Helfer ergänzen das Profil mit fokussierten Ergebnissen.
- **Model & tools / Modell & Tools:**
  - **EN:** Long-form flows (`job_ad`, `interview_guide`, `boolean_query`) run on `gpt-4o` with streaming; shorter lists (`skills`, `benefits`, `tasks`) use `gpt-4o-mini`. Setting `USE_CLASSIC_API=1` forces Chat Completions.
  - **DE:** Langformatige Ausgaben (`job_ad`, `interview_guide`, `boolean_query`) nutzen `gpt-4o` mit Streaming; kürzere Listen (`skills`, `benefits`, `tasks`) laufen auf `gpt-4o-mini`. Mit `USE_CLASSIC_API=1` erfolgt der Fallback auf Chat Completions.

### 6. Auto Re-ask Loop / Automatischer Nachfragen-Loop
- **Purpose / Zweck:**
  - **EN:** Replays the FQG until every `critical` question receives an answer, reducing manual intervention.
  - **DE:** Spielt den Nachfragen-Agenten erneut ab, bis jede `critical`-Frage beantwortet ist, und reduziert manuellen Aufwand.
- **Lifecycle / Ausführung:**
  - **EN/DE:** Activated when the “Auto follow-ups” toggle is enabled after extraction or after each automated answer.

### 7. Gap Analysis Agent / Gap-Analyse-Agent
- **Purpose / Zweck:**
  - **EN:** Combines vacancy text, ESCO enrichment, and RAG snippets into a concise report highlighting missing critical fields, recommended follow-ups, and next steps.
  - **DE:** Kombiniert Stellentext, ESCO-Anreicherung und RAG-Snippets zu einem kompakten Bericht mit fehlenden Pflichtfeldern, empfohlenen Nachfragen und nächsten Schritten.
- **Inputs / Eingaben:**
  - **EN:** Raw vacancy text, optional job title, ESCO metadata (if available), and retrieved snippets from `VECTOR_STORE_ID`.
  - **DE:** Rohtext der Stelle, optionaler Jobtitel, ESCO-Metadaten (falls vorhanden) sowie abgerufene Snippets aus `VECTOR_STORE_ID`.
- **Outputs / Ausgaben:**
  - **EN:** Markdown report (`assistant_report`), sorted follow-up questions, list of unresolved critical fields, and the enriched JSON profile.
  - **DE:** Markdown-Report (`assistant_report`), sortierte Nachfragen, Liste ungefüllter Pflichtfelder und das angereicherte JSON-Profil.
- **Model & tools / Modell & Tools:**
  - **EN/DE:** Leverages `llm.gap_analysis.analyze_vacancy`, which routes to `gpt-4o` for narrative output, while `retrieve_from_vector_store` performs `file_search` lookups when a vector store is configured.
- **Lifecycle / Ausführung:**
  - **EN:** Available via the Gap Analysis Streamlit page (`ui_views/gap_analysis.py`) and from wizard shortcuts that pre-fill the form after extraction.
  - **DE:** Über die Streamlit-Seite zur Gap-Analyse (`ui_views/gap_analysis.py`) abrufbar; der Wizard füllt das Formular nach der Extraktion automatisch vor.

## Tooling & Extensions / Werkzeuge & Erweiterungen

### Vector Retrieval Pipeline / Vektor-Retrieval-Pipeline
- **EN:** `llm/rag_pipeline.py` defines field-aware retrieval helpers (`FieldSpec`, `FieldExtractionContext`) that orchestrate per-field `file_search` calls. Agents reuse this module to attach provenance metadata and surface grounded suggestions.
- **DE:** `llm/rag_pipeline.py` stellt feldspezifische Retrieval-Helfer (`FieldSpec`, `FieldExtractionContext`) bereit, die `file_search`-Aufrufe pro Feld orchestrieren. Agenten nutzen das Modul, um Herkunftsmetadaten anzuhängen und begründete Vorschläge anzuzeigen.

### Gap Analysis Helpers / Gap-Analyse-Helfer
- **EN:** `llm/gap_analysis.py` supplies `GapContext`, ESCO lookup bridges, and prompt builders for the assistant report. It exposes `retrieve_from_vector_store` to fetch supporting snippets and `analyze_vacancy` to execute the full workflow.
- **DE:** `llm/gap_analysis.py` liefert `GapContext`, ESCO-Brücken und Prompt-Builder für den Assistentenbericht. `retrieve_from_vector_store` holt unterstützende Snippets, `analyze_vacancy` führt den kompletten Workflow aus.

### Wizard Graph Tools / Wizard-Graph-Tools
- **EN:** The `wizard_tools/` package registers Streamlit function tools (via the Agents SDK) to add, update, and connect wizard stages, ingest job ads, trigger extraction, and merge SME answers. Use these tools to experiment with custom agentic flows.
- **DE:** Das Paket `wizard_tools/` registriert Streamlit-Function-Tools (über das Agents SDK), um Wizard-Phasen hinzuzufügen, zu aktualisieren und zu verbinden, Stellenanzeigen zu laden, Extraktionen zu starten und SME-Antworten zusammenzuführen. Damit lassen sich agentische Eigenentwicklungen testen.

## Compliance & Roadmap / Compliance & Ausblick

### Compliance Sentinel *(planned) / geplant*
- **EN:** Will review generated content (job ads, interview guides, follow-ups) for GDPR/EEO compliance, surface violations, and block exports when necessary. Integrates with deliberate alignment routines in `llm/responses.py` and emits OpenTelemetry attributes.
- **DE:** Prüft künftig generierte Inhalte (Job-Ads, Interview-Guides, Nachfragen) auf DSGVO/EEO-Konformität, meldet Verstöße und kann Exporte blockieren. Bindet die Deliberate-Alignment-Routinen in `llm/responses.py` ein und versieht Spans mit OpenTelemetry-Attributen.

### Tech-Stack Miner *(planned) / geplant*
- **EN:** Detects missing technologies based on industry, ESCO data, and vector-store hints. Combines heuristics (`skill_market_insights.json`) with LLM reasoning, escalating ambiguous cases from `gpt-4o-mini` to `gpt-4o`.
- **DE:** Identifiziert fehlende Technologien anhand von Branche, ESCO-Daten und Vector-Store-Hinweisen. Kombiniert Heuristiken (`skill_market_insights.json`) mit LLM-Reasoning und eskaliert unklare Fälle von `gpt-4o-mini` auf `gpt-4o`.

### DEI Language Auditor *(planned) / geplant*
- **EN:** Post-processes job ads and interview questions to highlight biased phrasing and propose inclusive alternatives with severity levels for inline UI highlights.
- **DE:** Prüft Job-Ads und Interviewfragen nach voreingenommener Sprache, schlägt inklusive Alternativen vor und liefert Schweregrade für Inline-Hervorhebungen.

### Content Cost Router *(planned) / geplant*
- **EN:** Extends `config.py` routing logic to dynamically switch between GPT-5 mini and nano based on prompt complexity, context size, and output length, logging routing decisions for analytics.
- **DE:** Erweitert die Routing-Logik in `config.py`, um je nach Prompt-Komplexität, Kontextgröße und Ausgabelänge dynamisch zwischen GPT-5 mini und nano zu wechseln und Entscheidungen für Analysen zu protokollieren.

---

**EN:** Every agent returns a unified `ChatCallResult` (OK/usage/error/raw). UI components translate errors into friendly alerts with retry buttons, while exponential backoff handles transient rate limits. Refer to `llm/` for implementation details and `wizard.py` for integration points.

**DE:** Jeder Agent liefert einen einheitlichen `ChatCallResult` (OK/usage/error/raw). Die UI wandelt Fehler in verständliche Hinweise mit Retry-Schaltflächen um, und exponentielles Backoff fängt temporäre Rate-Limits ab. Implementierungsdetails stehen in `llm/`, Integrationspunkte in `wizard.py`.
