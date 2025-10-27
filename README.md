# Cognitive Staffing

**Cognitive Staffing** automates the extraction and enrichment of vacancy profiles from PDFs, URLs, or pasted text. It turns unstructured job ads into structured JSON, highlights missing data, and orchestrates multiple AI agents to draft follow-up questions, job ads, interview guides, and Boolean searches. By default all LLM calls run through the OpenAI **Responses API** using the `gpt-4o` family (`gpt-4o` for narrative/extraction workflows and `gpt-4o-mini` for short suggestions) so we can enforce structured outputs, stream long generations, and fall back gracefully when rate limits occur. If needed, set the `USE_CLASSIC_API` environment variable to route every call through the Chat Completions API instead.

![App Screenshot](images/app_screenshot.png)

## What's new in v1.0.0 / Neu in v1.0.0
- **Wizard overhaul & schema alignment:**
  **EN:** Every wizard step now shares a consistent header/subheader/intro layout that maps one-to-one to the `NeedAnalysisProfile` schema, ensuring exports remain perfectly synced.
  **DE:** Alle Wizard-Schritte nutzen jetzt ein einheitliches Header-/Subheader-/Intro-Layout mit direkter 1:1-Abbildung auf das `NeedAnalysisProfile`-Schema, sodass Exporte lückenlos synchron bleiben.
- **Multi-tone guidance for each step:**
  **EN:** New pragmatic, formal, and casual intro texts (EN/DE) explain what to capture on every step and adapt automatically to the selected language.
  **DE:** Neue pragmatische, formelle und lockere Intro-Texte (DE/EN) erläutern pro Schritt, welche Angaben benötigt werden, und passen sich automatisch der gewählten Sprache an.
- **Expanded AI assistance:**
  **EN:** Skills, benefits, and responsibilities now feature refreshed AI/ESCO suggestion buttons with better error handling, while the interview step generates full guides with graceful fallbacks.
  **DE:** Skills, Benefits und Verantwortlichkeiten erhalten aktualisierte KI-/ESCO-Vorschlagsbuttons mit robuster Fehlerbehandlung, und der Interview-Schritt erzeugt komplette Leitfäden inklusive Fallbacks.
- **Design system & mobile polish:**
  **EN:** Light/dark themes share one design token set with improved spacing, focus states, and responsive navigation for mobile recruiters.
  **DE:** Light-/Dark-Themes greifen auf einen gemeinsamen Design-Token-Pool mit optimierten Abständen, Fokuszuständen und responsiver Navigation für mobile Recruiter:innen zurück.

## Feature Highlights
- **Structured extraction:** JSON schemas and Pydantic validation keep 20+ vacancy fields aligned with `NeedAnalysisProfile`. Locked fields such as **job_title** or **company** are auto-filled when rule matches fire and stay protected until you unlock them.
- **Interactive follow-ups:** A Follow-up Question Generator agent produces prioritized follow-up questions with suggestion chips. When ESCO metadata is available the assistant injects normalized essential skills into the prompts, and the auto re-ask loop keeps rerunning critical prompts until every must-have field is answered.
- **ESCO integration:** When enabled, the ESCO enricher normalizes job titles, proposes essential skills, and flags missing competencies directly in the UI.
- **AI-assisted suggestions:** Dedicated helpers surface responsibilities, skills, benefits, boolean strings, interview guides, and polished job ads. Responses stream live by default so the UI stays responsive during longer generations, and the requirements, role, and compensation steps now ship with on-demand “Suggest responsibilities”, “Suggest additional skills”, and “Suggest benefits” actions that factor in existing context to avoid duplicates.
- **Step intros & captions / Schritt-Intros & Hinweise:**
  **EN:** Each wizard page opens with a localized caption in your chosen tone so teams immediately understand which details matter most.
  **DE:** Jede Wizard-Seite startet mit einer lokalisierten Caption im gewünschten Tonfall, damit Teams sofort wissen, welche Angaben entscheidend sind.
- **Guided wizard sections / Geführte Wizard-Abschnitte:**
  **EN:** Steps are grouped into Onboarding, Company, Team & Structure, Role & Tasks, Skills & Requirements, Compensation, Hiring Process, and Summary so recruiters can follow a consistent flow with inline help for each section.
  **DE:** Schritte sind in Onboarding, Unternehmen, Team & Struktur, Rolle & Aufgaben, Skills & Anforderungen, Vergütung, Prozess und Zusammenfassung gegliedert, damit Recruiter:innen einem einheitlichen Ablauf mit Inline-Hilfen folgen können.
- **Tone control / Tonalitätssteuerung:**
  **EN:** Choose between concise, professional, or casual writing styles before generating job ads, interview guides, or follow-up emails.
  **DE:** Wähle vor der Generierung von Stellenanzeigen, Interview-Guides oder Follow-up-E-Mails zwischen prägnantem, professionellem oder lockerem Schreibstil.
- **Automatic company research / Automatische Unternehmensrecherche:**
  **EN:** After uploading a job ad the wizard fetches mission, culture, and approximate company size from the web to pre-fill the company section.
  **DE:** Nach dem Upload einer Ausschreibung ruft der Wizard Mission, Kultur und ungefähre Unternehmensgröße aus dem Web ab und füllt den Unternehmensbereich vor.
- **Analysis helpers / Analyse-Helfer:**
  **EN:** Deterministic tools expose salary benchmarks, currency conversion with cached FX rates, and ISO date normalisation so the assistant can ground reasoning steps without extra API calls.
  **DE:** Deterministische Helfer liefern Gehaltsbenchmarks, Währungsumrechnung mit zwischengespeicherten FX-Kursen und ISO-Datumsnormalisierung, damit der Assistent ohne zusätzliche APIs fundiert begründen kann.
- **Vector-store enrichment:** Provide `VECTOR_STORE_ID` to let the RAG agent retrieve supporting snippets via OpenAI **file_search**, seeding better suggestions when the uploaded job ad is sparse.
- **Multi-model routing:** The router sends high-complexity tasks to `gpt-4o` and lightweight lookups to `gpt-4o-mini` by default. Administrators can still pin a specific tier via configuration (for example by setting `OPENAI_MODEL`), but the sidebar now focuses on automated routing.
- **Gap analysis workspace / Gap-Analyse-Arbeitsbereich:**
  **EN:** Launch the **Gap analysis** view to combine ESCO metadata, retrieved snippets, and vacancy text into an executive-ready report that highlights missing information and next steps.
  **DE:** Öffne die Ansicht **Gap-Analyse**, um ESCO-Metadaten, abgerufene Snippets und Ausschreibungstext zu einem Management-tauglichen Bericht mit offenen Punkten und nächsten Schritten zu verbinden.
- **Deliberate UX:** Wizard sections combine inline help, locking indicators, and progress-aware navigation so teams always know why a field is frozen, which suggestions are pending, and how far they are from completion. Branded dark/light themes align with Cognitive Staffing colors.

## Model Routing & Cost Controls / Modellrouting & Kostensteuerung

- **Content cost router / Kostenrouter für Inhalte**
  **EN:** Each request runs through a prompt cost router that inspects token length and hard-to-translate compounds before selecting the cheapest suitable tier. Short, simple prompts stay on `gpt-4o-mini`, while complex or multilingual payloads automatically escalate to `gpt-4o` for higher quality. Power users can still force GPT-5 mini/nano for premium reasoning.
  **DE:** Jede Anfrage durchläuft einen Kostenrouter, der Tokenlänge und schwer übersetzbare Komposita prüft, bevor das günstigste passende Modell gewählt wird. Kurze, einfache Prompts bleiben auf `gpt-4o-mini`, komplexe oder mehrsprachige Eingaben wechseln automatisch auf `gpt-4o`, um Qualität ohne manuelles Feintuning sicherzustellen. Bei Bedarf lassen sich weiterhin GPT-5 mini/nano für Premium-Reasoning erzwingen.
- **Fallback chain (GPT-5 mini → GPT-4o → GPT-4 → GPT-3.5) / Fallback-Kette (GPT-5 mini → GPT-4o → GPT-4 → GPT-3.5)**
  **EN:** When the primary model is overloaded or deprecated the platform now retries with the expanded chain `gpt-5.1-mini → gpt-4o → gpt-4 → gpt-3.5-turbo`. Each downgrade is recorded in telemetry so we can spot chronic outages.
  **DE:** Meldet die API, dass das Primärmodell überlastet oder abgekündigt ist, läuft der neue Fallback-Pfad `gpt-5.1-mini → gpt-4o → gpt-4 → gpt-3.5-turbo`. Jeder Schritt wird im Telemetrie-Stream protokolliert, um anhaltende Störungen sichtbar zu machen.
- **Model override via configuration / Modell-Override über Konfiguration**
  **EN:** Use environment variables or secrets (e.g., `OPENAI_MODEL` or `st.session_state["model_override"]`) to pin a specific tier when necessary. Clearing the override restores automatic routing (`gpt-4o` / `gpt-4o-mini`) and fallback behaviour.
  **DE:** Setze bei Bedarf Umgebungsvariablen oder Secrets (z. B. `OPENAI_MODEL` oder `st.session_state["model_override"]`), um ein bestimmtes Modell festzulegen. Ohne Override greift wieder das automatische Routing (`gpt-4o` / `gpt-4o-mini`) inklusive Fallback-Kette.

## Architecture at a Glance
The Streamlit entrypoint (`app.py`) wires UI components from `components/` and the multi-step graph in `wizard.py` into a shared `st.session_state`. Domain rules in `core/` and `question_logic.py` keep the vacancy schema aligned with UI widgets and exports. Agents (see [AGENTS.md](AGENTS.md)) call into `llm/` helpers that return a unified `ChatCallResult`, manage retries, and execute registered tools.

```
streamlit app.py
  ├─ wizard.py + components/      → build the UI flow & session state
  │    └─ wizard_tools/           → Streamlit function tools (ingest, reruns, SME merge)
  ├─ core/ + question_logic.py    → vacancy domain logic & schema synchronisation
  └─ agents (AGENTS.md)
       ├─ llm/responses.py        → ChatCallResult wrapper & tool runner
       │    └─ llm/rag_pipeline.py → OpenAI file_search tool (VECTOR_STORE_ID)
       └─ ingest/ + integrations/ → PDF/HTML/OCR loaders, ESCO API, vector stores
```

All LLM prompts are defined in `prompts/registry.yaml` and loaded via the shared
`prompt_registry` helper, keeping Streamlit deployments and CLI utilities in sync.

## RecruitingWizard Schema – Single Source of Truth / Master-Schema RecruitingWizard

**EN:** The new RecruitingWizard master schema (see `core/schema.py`) unifies the
company, team, role, skills, benefits, interview process, and summary payloads that
power the wizard UI, downstream logic, and exports. Each field is represented by a
typed Pydantic model, and `KEYS_CANONICAL` exposes the canonical dot-paths so other
modules (`wizard/`, `question_logic.py`, exports) stay in sync. Source tracking and
gap analysis are first-class citizens via `SourceMap` (`user` | `extract` | `web`
with confidence and `source_url`) and `MissingFieldMap` entries that carry owners
and reminders. Enable the schema by setting `SCHEMA_WIZARD_V1=1`; a feature flag is
kept for gradual rollout. The helper in `core/schema_defaults.py` provides a sample
payload for tests, while `exports/models.py` wraps validated payloads for JSON/MD
deliverables.

**DE:** Das neue RecruitingWizard-Masterschema (`core/schema.py`) bündelt Unternehmens-,
Team-, Rollen-, Skill-, Benefit-, Interview- und Zusammenfassungsdaten als zentrale
Wahrheit für Wizard, Logik und Exporte. Alle Felder sind typisiert, `KEYS_CANONICAL`
liefert die kanonischen Dot-Pfade, damit UI (`wizard/`), Business-Logik und Exporte
identisch bleiben. `SourceMap` (`user` | `extract` | `web` mit Confidence &
`source_url`) sowie `MissingFieldMap` inklusive Owner/Reminder halten Lücken sichtbar.
Die Aktivierung erfolgt über `SCHEMA_WIZARD_V1=1`; das Feature-Flag ermöglicht einen
gestaffelten Rollout. `core/schema_defaults.py` stellt ein Beispieldataset für Tests
bereit, `exports/models.py` kapselt validierte Payloads für JSON- und Markdown-Exports.

> **Migration note / Migrationshinweis:** Align wizard widgets and downstream
> processors with the canonical keys from `core/schema.py::KEYS_CANONICAL`. During the
> rollout keep legacy handling behind the feature flag disabled until UI and exports
> reference the new schema end-to-end.

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/KleinerBaum/cognitivestaffing.git
cd cognitivestaffing
```

### 2. Create a virtual environment
```bash
python3.11 -m venv .venv  # Python 3.11
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

> **Deployment config / Deployment-Konfiguration:**
> **EN:** Streamlit Community Cloud deployments read `infra/deployment.toml`; keep `[python].requirements` set to `requirements.txt` to silence duplicate-requirements warnings.
> **DE:** Streamlit-Community-Deployments lesen `infra/deployment.toml`; belasse `[python].requirements` auf `requirements.txt`, um Warnungen zu mehrfachen Requirements-Dateien zu vermeiden.

### 4. Provide OpenAI credentials
Set environment variables (or configure `.streamlit/secrets.toml` under the `openai` key):
```bash
export OPENAI_API_KEY="sk-..."
# Optional overrides
export OPENAI_BASE_URL="https://api.openai.com/v1"          # use https://eu.api.openai.com/v1 for EU residency
export OPENAI_MODEL="gpt-4o"                                  # default model override (balanced gpt-4o)
export OPENAI_REQUEST_TIMEOUT="120"                          # seconds; extend for long-running generations
export OPENAI_ORGANIZATION="org_XXXXXXXXXXXX"                # optional: route usage to a specific organization
export OPENAI_PROJECT="proj_XXXXXXXXXXXX"                    # optional: scope API traffic to an OpenAI project
export REASONING_EFFORT="medium"                             # minimal | low | medium | high
export VERBOSITY="medium"                                     # low | medium | high (Antwort-Detailgrad)
export VECTOR_STORE_ID="vs_XXXXXXXXXXXXXXXX"                 # enable RAG lookups (optional)
export OTEL_EXPORTER_OTLP_ENDPOINT="https://otel.example/v1/traces"  # optional tracing
export OTEL_SERVICE_NAME="cognitive-staffing"
export USE_CLASSIC_API="1"                                    # set to 1 to force Chat Completions (Responses bleibt Standard)
```
You can also add `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_REQUEST_TIMEOUT`, `OPENAI_ORGANIZATION`, `OPENAI_PROJECT`, `VERBOSITY`, and `VECTOR_STORE_ID` to `st.secrets` if you prefer Streamlit's secret storage. When `OPENAI_BASE_URL` points to `https://eu.api.openai.com/v1`, all traffic stays within the EU region.

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
2. **Review the overview:** The sidebar highlights which fields were rule-matched, inferred by AI, or still missing. Use the inline help to understand why fields are locked or which follow-ups remain outstanding.
3. **Answer follow-ups:** The Follow-up Question Generator asks targeted questions. Enable *Auto follow-ups* to let the agent re-run until all critical gaps are closed.
4. **Enrich requirements:** Accept AI suggestions for skills, benefits, salary ranges, and responsibilities. Tooltips explain why suggestions might be empty (e.g., locked fields, missing context, or disabled RAG).
   - **EN:** Use the ESCO search input in the requirements step to look up occupations and import their essential skills with one click.
   - **DE:** Nutze die ESCO-Suche im Anforderungsschritt, um Berufe zu finden und deren Pflicht-Skills direkt zu übernehmen.
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

## Prompt Registry / Prompt-Registry

- **EN:** All LLM system and user templates now live in `prompts/registry.yaml`. Each entry can define a `system` message, optional locale variants, and metadata like model hints. Import `prompts.prompt_registry` to fetch or format templates dynamically (e.g., `prompt_registry.format("llm.extraction.context.system", function_name="NeedAnalysisProfile")`). Updating or adding prompts no longer requires code changes—edit the YAML file and the wizard picks up the change on the next run.
- **DE:** Sämtliche System- und User-Prompts der LLMs liegen jetzt in `prompts/registry.yaml`. Jede Registry-Zeile kann eine `system`-Nachricht, optionale Sprachvarianten und Metadaten wie Modellhinweise enthalten. Über `prompts.prompt_registry` lassen sich Templates dynamisch abrufen bzw. mit Parametern formatieren (z. B. `prompt_registry.format("llm.extraction.context.system", function_name="NeedAnalysisProfile")`). Neue oder geänderte Prompts erfordern keinen Code-Change mehr – YAML anpassen, App neu starten, fertig.

## Further Reading
- [AGENTS.md](AGENTS.md) for an overview of every autonomous agent (Follow-up generator, ESCO enricher, RAG assistant, compliance plans, etc.).
- [docs/](docs/) for schema references, JSON pipelines, and changelogs.

Happy hiring!
