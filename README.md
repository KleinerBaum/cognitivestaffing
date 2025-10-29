# Cognitive Staffing

![Coverage badge showing minimum 88 percent](https://img.shields.io/badge/coverage-88%25-brightgreen)

**Cognitive Staffing** automates the extraction and enrichment of vacancy profiles from PDFs, URLs, or pasted text. It turns unstructured job ads into structured JSON, highlights missing data, and orchestrates multiple AI agents to draft follow-up questions, job ads, interview guides, and Boolean searches. By default, all LLM calls run through the OpenAI **Responses API** using cost-effective models: lightweight tasks run on `gpt-4o-mini` (aka `gpt-4.1-nano`) while reasoning-heavy flows (summaries, explanations, document rewrites) escalate to `gpt-5-nano` (OpenAI endpoint `gpt-5.1-nano`). This setup lets us enforce structured outputs, stream long generations, and fall back gracefully when rate limits occur. If needed, set the `USE_CLASSIC_API` environment variable to route all calls through the standard Chat Completions API instead.

![App Screenshot](images/app_screenshot.png)

## Version

- **EN:** Current release: **v1.1.0** (November 2025) – see below for highlights.
- **DE:** Aktuelle Version: **v1.1.0** (November 2025) – Highlights siehe unten.

## Unreleased

- **EN:** CI now enforces a minimum 88% coverage, uploads XML/HTML reports, and keeps `llm`-tagged pytest cases opt-in to guard heuristics without blocking offline contributors.
  **DE:** Die CI erzwingt jetzt mindestens 88 % Testabdeckung, lädt XML-/HTML-Berichte hoch und behandelt `llm`-markierte Pytest-Cases optional, damit Heuristiken geschützt bleiben und Offline-Contributor:innen weiterarbeiten können.
- **EN:** Hardened optional profile URL sanitisation so canonicalisation and wizard updates trim blanks to `None`, preventing schema resets.
  **DE:** Optionale Profil-URLs weiter gehärtet: Kanonisierung und Wizard-Updates kürzen leere Werte jetzt auf `None`, sodass keine Schema-Resets mehr ausgelöst werden.
- **EN:** Streamlined dependency management so `requirements.txt` remains the single source of truth and deployment no longer reports multiple requirement files.
  **DE:** Abhängigkeitsverwaltung gestrafft, sodass `requirements.txt` die einzige Quelle bleibt und beim Deployment keine Warnung zu mehreren Requirements-Dateien mehr erscheint.

## Testing / Tests

- **EN:** Run `ruff format`, `ruff check`, and `mypy --config-file pyproject.toml` before executing `coverage run -m pytest -q` (the default marker expression skips `llm` tests; add `-m llm` when an OpenAI key is configured). Keep total coverage ≥88% so CI stays green and XML/HTML artifacts remain available for review.
- **DE:** Führe `ruff format`, `ruff check` und `mypy --config-file pyproject.toml` aus und starte anschließend `coverage run -m pytest -q` (standardmäßig werden `llm`-Tests übersprungen; mit konfiguriertem OpenAI-Key kannst du `-m llm` ergänzen). Halte die Gesamtabdeckung bei ≥88 %, damit die CI grün bleibt und XML-/HTML-Artefakte für das Review bereitstehen.

## What's new in v1.1.0 / Neu in v1.1.0

- **EN:** Normalise wizard widget defaults via `_ensure_widget_state()` so text inputs and list editors seed before rendering, avoiding Streamlit "Cannot set widget" errors on reruns.
  **DE:** Normalisiert die Widget-Defaults im Wizard über `_ensure_widget_state()`, damit Textfelder und Listen-Editoren vor dem Rendern initialisiert werden und beim erneuten Ausführen keine "Cannot set widget"-Fehler mehr auftreten.
- **EN:** Clean up company contact phones and websites across the wizard so noisy entries are normalised and cleared fields store `None` in the profile.
  **DE:** Bereinigt Unternehmens-Telefonnummern und Websites im Wizard, normalisiert unruhige Eingaben und speichert geleerte Felder als `None` im Profil.
- **EN:** Disable all AI suggestion buttons and generation actions when no OpenAI API key is configured, displaying a bilingual lock hint instead of triggering backend calls.
  **DE:** Deaktiviert sämtliche KI-Vorschlagsbuttons und Generierungsaktionen, sobald kein OpenAI-API-Schlüssel hinterlegt ist, und zeigt stattdessen einen zweisprachigen Hinweis an.
- **EN:** Unified Responses API retry handling now logs warnings and automatically falls back to chat completions or static content when structured calls fail or return invalid JSON.
  **DE:** Vereinheitlichte Responses-Retry-Logik protokolliert Warnungen und schaltet automatisch auf Chat-Completions oder statische Inhalte um, wenn strukturierte Aufrufe scheitern oder ungültiges JSON liefern.
- **EN:** Enforced full NeedAnalysisProfile ↔ wizard alignment: every schema field now has a canonical `ProfilePaths` entry, appears in the wizard panels, and propagates into exports with regression tests guarding drift.
  **DE:** Vollständige NeedAnalysisProfile↔Wizard-Ausrichtung umgesetzt: Jedes Schemafeld besitzt nun einen kanonischen `ProfilePaths`-Eintrag, wird in den Wizard-Panels angezeigt und in Exporte übernommen, abgesichert durch Regressionstests gegen Abweichungen.
- **EN:** Refined the salary sidebar: the panel now highlights the latest estimate with its source, charts top factors via Plotly, and falls back to curated benefit shortlists whenever the AI returns no suggestions.
  **DE:** Salary-Sidebar überarbeitet: Die Ansicht zeigt nun die aktuelle Schätzung samt Quelle, visualisiert die wichtigsten Einflussfaktoren mit Plotly und blendet bei ausbleibenden KI-Vorschlägen automatisch die kuratierte Benefit-Shortlist ein.
- **EN:** Sidebar branding overrides let you upload a logo, pick a brand colour, and edit the claim; exports and job ads now embed that metadata by default.
  **DE:** Branding-Overrides in der Sidebar ermöglichen Logo-Uploads, die Auswahl der Markenfarbe und das Bearbeiten des Claims; Exporte und Stellenanzeigen übernehmen diese Metadaten automatisch.

## Branding Integration / Branding-Integration

**EN:** The wizard now recognises employer branding assets automatically. When a career page URL is provided, Cognitive Staffing detects the company logo, dominant brand colour, and slogan, then applies them to the sidebar hero, exports, and downstream JSON (`company.logo_url`, `company.brand_color`, `company.claim`). The screenshot below shows an example sidebar that picked up a logo and tone-on-tone accent colour without any manual configuration.

**DE:** Der Wizard erkennt Employer-Branding-Assets jetzt automatisch. Sobald eine Karriereseiten-URL vorliegt, ermittelt Cognitive Staffing Logo, Hauptfarbe und Claim des Unternehmens und übernimmt sie in die Sidebar, Exporte sowie das JSON (`company.logo_url`, `company.brand_color`, `company.claim`). Der Screenshot unten zeigt eine Sidebar, die Logo und Akzentfarbe ohne manuelle Einstellungen übernommen hat.

![Branding example sidebar](images/branding_sidebar.svg)

**EN:** If detection misses assets you can open the sidebar branding settings to upload a logo or choose a fallback colour. The job-ad generator now feeds the slogan and brand colour into its prompt metadata and Markdown fallback, ensuring downstream exports keep the employer voice.

**DE:** Falls die Erkennung keine Assets findet, kannst du in den Branding-Einstellungen der Sidebar ein Logo hochladen oder eine Ersatzfarbe wählen. Die Stellenanzeigengenerierung übergibt Claim und Markenfarbe an Prompt-Metadaten und Markdown-Fallback, damit Exporte den Arbeitgeberton zuverlässig mitführen.

> **Limitations / Einschränkungen**
>
> **EN:** Branding detection currently targets public websites. Private portals or PDF-only uploads fall back to the default Cognitive Staffing theme.
>
> **DE:** Die Branding-Erkennung funktioniert derzeit für öffentliche Websites. Private Portale oder reine PDF-Uploads nutzen weiterhin das Standard-Theme.

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
- **Structured extraction:** JSON schemas and Pydantic validation keep 20+ vacancy fields aligned with the `NeedAnalysisProfile` model. Locked fields such as **job_title** or **company** are auto-filled when rule matches fire and remain protected until explicitly unlocked.
- **Interactive follow-ups:** A Follow-up Question Generator agent produces prioritized follow-up questions with suggestion chips. When ESCO metadata is available, the assistant injects normalized essential skills into its prompts, and an auto re-ask loop will keep rerunning critical questions until every must-have field is answered.
- **ESCO integration:** When enabled, the ESCO enricher normalizes job titles, proposes essential skills, and flags missing competencies directly in the UI.
- **AI-assisted suggestions:** Dedicated helper agents surface responsibilities, skills, benefits, boolean strings, interview guides, and polished job ads. Responses stream live by default so the UI remains responsive during longer generations. The requirements, role, and compensation steps now include on-demand “Suggest responsibilities”, “Suggest additional skills”, and “Suggest benefits” actions that take into account existing inputs to avoid duplicates.
- **Step intros & captions / Schritt-Intros & Hinweise:**  
  **EN:** Each wizard page opens with a localized introductory caption (in the chosen tone) so teams immediately know which details matter most on that step.  
  **DE:** Jede Wizard-Seite startet mit einer lokalisierten Einleitung im gewählten Tonfall, damit Teams sofort wissen, welche Angaben auf diesem Schritt entscheidend sind.
- **Guided wizard sections / Geführte Wizard-Abschnitte:**  
  **EN:** Steps are grouped into Onboarding, Company, Team & Structure, Role & Tasks, Skills & Requirements, Compensation, Hiring Process, and Summary, so recruiters can follow a consistent flow with inline help for each section.  
  **DE:** Schritte sind in Onboarding, Unternehmen, Team & Struktur, Rolle & Aufgaben, Skills & Anforderungen, Vergütung, Prozess und Zusammenfassung gegliedert, damit Recruiter:innen einem einheitlichen Ablauf mit Inline-Hilfen pro Abschnitt folgen können.
- **Tone control / Tonalitätssteuerung:**  
  **EN:** Choose between concise, professional, or casual writing styles before generating job ads, interview guides, or follow-up emails.  
  **DE:** Wähle vor der Generierung von Stellenanzeigen, Interview-Guides oder Follow-up-E-Mails zwischen einem prägnanten, professionellen oder lockeren Schreibstil.
- **Automatic company research / Automatische Unternehmensrecherche:**  
  **EN:** After uploading a job ad, the wizard fetches the company’s mission, culture, and approximate size from the web to pre-fill the company section.  
  **DE:** Nach dem Upload einer Stellenanzeige ruft der Wizard Mission, Kultur und ungefähre Unternehmensgröße aus dem Web ab und füllt den Unternehmensbereich damit vor.
- **Normalization & JSON repair / Normalisierung & JSON-Reparatur:**  
  **EN:** A repository-wide normalization pipeline trims noise, harmonizes gender-specific terms and locations, uppercases country codes, and automatically repairs malformed profile JSON via the OpenAI Responses API if validation fails.  
  **DE:** Eine Repository-weite Normalisierung entfernt Rauschen, bereinigt Gender-Zusätze und Ortsangaben, wandelt Ländercodes in Großbuchstaben und repariert ungültiges Profil-JSON bei Validierungsfehlern automatisch über die OpenAI-Responses-API.
- **Branding auto-detect / Branding-Autoerkennung:**  
  **EN:** Brand assets (logo, favicon, dominant color, and company claim) are scraped from provided career page URLs, cached, and injected into the wizard’s sidebar, exports, and editing forms.  
  **DE:** Branding-Assets (Logo, Favicon, dominante Farbe und Unternehmensclaim) werden von angegebenen Karriereseiten extrahiert, zwischengespeichert und im Wizard-Sidebar, in Exporten und in den Eingabemasken angezeigt.
- **Analysis helpers / Analyse-Helfer:**
  **EN:** Deterministic helper tools provide salary benchmarks, currency conversion with cached FX rates, and ISO date normalization, allowing the assistant to ground certain reasoning steps without extra API calls.
  **DE:** Deterministische Helfer liefern Gehalts-Benchmarks, Währungsumrechnung mit zwischengespeicherten FX-Kursen und ISO-Datumsnormalisierung, sodass der Assistent ohne zusätzliche APIs fundierte Herleitungen vornehmen kann.
- **Suggestion failover / Vorschlags-Failover:**
  **EN:** If the OpenAI Responses endpoint is unavailable or `USE_CLASSIC_API=1`, skill and benefit suggestions automatically fall back to the classic Chat Completions backend; persistent failures return curated static benefit shortlists so the UI never blocks.
  **DE:** Fällt der OpenAI-Responses-Endpunkt aus oder ist `USE_CLASSIC_API=1` gesetzt, weichen Skill- und Benefit-Vorschläge automatisch auf die klassische Chat-Completions-API aus; bei dauerhaften Fehlern liefern kuratierte statische Benefit-Shortlists weiterhin nutzbare Ergebnisse.
- **Vector-store enrichment:** If you set a `VECTOR_STORE_ID`, the RAG agent will retrieve supporting snippets via OpenAI **file_search**, yielding better suggestions when the uploaded job ad is sparse on details.
- **Multi-model routing / Modellrouting:**
  **EN:** The router now uses `gpt-4o-mini` (GPT-4.1-nano) for lightweight lookups and escalates summarisation, explanation, and planning flows to `gpt-5-nano` (`gpt-5.1-nano` endpoint), with fallbacks through `gpt-4o` and legacy GPT-4 when capacity issues arise. Administrators can still override the model via configuration (for example by setting `OPENAI_MODEL`), but automated selection is the default.
  **DE:** Der Router nutzt standardmäßig `gpt-4o-mini` (GPT-4.1-nano) für leichte Abfragen und hebt Zusammenfassungen, Erklärungen und Planungen auf `gpt-5-nano` (Endpoint `gpt-5.1-nano`), inklusive Fallbacks über `gpt-4o` und das klassische GPT-4 bei Kapazitätsproblemen. Administratoren können per Konfiguration (z. B. mit `OPENAI_MODEL`) weiterhin ein bestimmtes Modell fest vorgeben, aber normalerweise erfolgt die Modellauswahl automatisch.
- **Gap analysis workspace / Gap-Analyse-Arbeitsbereich:**  
  **EN:** Launch the **Gap analysis** view to combine ESCO metadata, retrieved snippets, and vacancy text into an executive-ready report that highlights missing information and next steps.  
  **DE:** Öffne die Ansicht **Gap-Analyse**, um ESCO-Metadaten, gefundene Snippets und Ausschreibungstext zu einem Management-tauglichen Bericht zu kombinieren, der fehlende Informationen und nächste Schritte hervorhebt.

## Model Routing & Cost Controls / Modellrouting & Kostensteuerung

- **Content cost router / Kostenrouter für Inhalte**
  **EN:** Each request runs through a prompt cost router that inspects the token length and content before selecting the cheapest suitable tier. Lightweight prompts execute on `gpt-4o-mini`, while tasks requiring deeper reasoning automatically escalate to `gpt-5-nano` (`gpt-5.1-nano`). When quality risks remain high the chain continues through `gpt-4o` and even `gpt-4`. Power users can still force a specific tier when necessary.
  **DE:** Jede Anfrage durchläuft einen Kostenrouter, der Tokenlänge und Inhalt prüft, bevor das günstigste passende Modell gewählt wird. Leichte Prompts laufen auf `gpt-4o-mini`, während Aufgaben mit höherem Reasoning-Bedarf automatisch auf `gpt-5-nano` (`gpt-5.1-nano`) eskalieren. Bleiben Qualitätsrisiken bestehen, führt die Kette weiter über `gpt-4o` bis hin zu `gpt-4`. Bei Bedarf lässt sich weiterhin gezielt eine bestimmte Modellstufe erzwingen.
- **Fallback chain (GPT-5 nano → GPT-5 mini → GPT-4o → GPT-4 → GPT-3.5) / Fallback-Kette (GPT-5 nano → GPT-5 mini → GPT-4o → GPT-4 → GPT-3.5)**
  **EN:** When the primary model is overloaded or deprecated, the platform retries with the chain `gpt-5-nano → gpt-5-mini → gpt-4o → gpt-4 → gpt-3.5-turbo` (resolving to the API endpoints `gpt-5.1-nano` → `gpt-5.1-mini` …). Each downgrade is recorded in telemetry so we can spot chronic outages.
  **DE:** Meldet die API, dass das Primärmodell überlastet oder abgekündigt ist, greift jetzt der Fallback-Pfad `gpt-5-nano → gpt-5-mini → gpt-4o → gpt-4 → gpt-3.5-turbo` (technisch `gpt-5.1-nano` → `gpt-5.1-mini` …). Jeder Herunterstufungsversuch wird im Telemetrie-Stream protokolliert, um dauerhafte Störungen erkennbar zu machen.
- **Model override via configuration / Modell-Override über Konfiguration**
  **EN:** Use environment variables or secrets (e.g., set `OPENAI_MODEL` or `st.session_state["model_override"]`) to pin a specific model tier if necessary. Clearing the override restores automatic cost-based routing and the normal fallback chain.
  **DE:** Setze bei Bedarf Umgebungsvariablen oder Secrets (z. B. `OPENAI_MODEL` oder `st.session_state["model_override"]`), um ein bestimmtes Modell fest vorzugeben. Ohne Override greift wieder das automatische, kostenbasierte Routing inklusive Fallback-Kette.

## LLM configuration & fallbacks / LLM-Konfiguration & Fallbacks

**EN:**

- `USE_RESPONSES_API` (default `1`) routes all structured calls through the OpenAI Responses API with enforced JSON schemas and tool support. Setting this flag to `0` (or `False`) automatically toggles `USE_CLASSIC_API=1` so every request uses the Chat Completions client instead.
- `USE_CLASSIC_API=1` forces the legacy chat backend even when Responses would normally be selected. Both suggestion and extraction pipelines retry on Responses errors first, then cascade to chat, and finally fall back to curated static copy (for example, benefit shortlists) if the API keeps failing.
- When no `OPENAI_API_KEY` is configured the UI disables all AI buttons and shows a bilingual lock banner. Providing the key via environment variables or Streamlit secrets re-enables the features immediately.
- `REASONING_EFFORT` controls the "genau" (precision) mode: higher levels switch suggestion/extraction calls to a stronger reasoning model tier while keeping standard flows on `gpt-4o-mini`.
- `OPENAI_BASE_URL` can be set to `https://eu.api.openai.com/v1` (or another allowed endpoint) to keep traffic within the EU region; other OpenAI secrets (`OPENAI_MODEL`, `OPENAI_PROJECT`, `OPENAI_ORGANIZATION`, `OPENAI_REQUEST_TIMEOUT`) are honoured as well.
- `VECTOR_STORE_ID` activates RAG lookups through OpenAI file search. Without it the assistant skips retrieval but still completes suggestions using Responses or the chat fallback chain.

**DE:**

- `USE_RESPONSES_API` (Standard `1`) leitet strukturierte Aufrufe über die OpenAI-Responses-API mit JSON-Schema-Prüfung und Tool-Support. Wird das Flag auf `0` (oder `False`) gesetzt, schaltet sich automatisch `USE_CLASSIC_API=1` ein und sämtliche Requests laufen über die Chat-Completions-Schnittstelle.
- `USE_CLASSIC_API=1` erzwingt den Legacy-Chat-Client, auch wenn Responses normalerweise gewählt würde. Vorschlags- und Extraktionspipelines versuchen zunächst Responses, wechseln danach auf Chat und greifen zuletzt auf kuratierte statische Inhalte (z. B. Benefit-Shortlists) zurück, wenn die API dauerhaft fehlschlägt.
- Ohne konfigurierten `OPENAI_API_KEY` deaktiviert die Oberfläche alle KI-Schaltflächen und blendet einen zweisprachigen Sperr-Hinweis ein. Sobald der Schlüssel via Umgebungsvariable oder Streamlit-Secrets hinterlegt ist, stehen die Funktionen wieder zur Verfügung.
- Über `REASONING_EFFORT` wird der Modus „genau“ gesteuert: Höhere Stufen nutzen für Vorschläge/Extraktionen stärkere Reasoning-Modelle, während Standardflüsse auf `gpt-4o-mini` verbleiben.
- Mit `OPENAI_BASE_URL` lässt sich beispielsweise `https://eu.api.openai.com/v1` konfigurieren, um Aufrufe innerhalb der EU zu halten; weitere OpenAI-Secrets (`OPENAI_MODEL`, `OPENAI_PROJECT`, `OPENAI_ORGANIZATION`, `OPENAI_REQUEST_TIMEOUT`) werden ebenfalls ausgewertet.
- `VECTOR_STORE_ID` aktiviert RAG-Abfragen über OpenAI File Search. Ohne gesetzte ID überspringt der Assistent die Recherche, führt Vorschläge aber weiterhin über Responses oder die Chat-Fallback-Kette aus.

## Architecture at a Glance

The Streamlit entry point (`app.py`) wires UI components from `components/` and the multi-step flow in `wizard.py` into a shared `st.session_state`. Domain rules in `core/` and `question_logic.py` keep the vacancy schema aligned with UI widgets and exports. Agents (see [AGENTS.md](AGENTS.md)) delegate LLM calls to `llm/` helpers that return a unified `ChatCallResult`, manage retries, and execute any registered tools.

streamlit app.py
├─ wizard.py + components/ → builds the UI flow & session state
│ └─ wizard_tools/ → Streamlit function tools (ingest, reruns, SME merge)
├─ core/ + question_logic.py → vacancy domain logic & schema synchronization
└─ agents (AGENTS.md)
├─ llm/responses.py → ChatCallResult wrapper & tool runner
│ └─ llm/rag_pipeline.py → OpenAI file_search tool (uses VECTOR_STORE_ID)
└─ ingest/ + integrations/ → PDF/HTML/OCR loaders, ESCO API clients, vector store handlers


All LLM prompts are defined in `prompts/registry.yaml` and loaded via a shared `prompt_registry` helper, keeping the Streamlit UI and CLI utilities in sync.

## UI Binding Rules / UI-Bindungsregeln

**EN:**

- Always get widget default values via `wizard._logic.get_value("<path>")`. The profile stored in `st.session_state[StateKeys.PROFILE]` is the single source of truth and already includes schema defaults.
- Use schema paths (e.g., `"company.name"`, `"location.primary_city"`) as widget keys. Avoid binding inputs to legacy keys like `ui.*` when reading data.
- Prefer using the helper functions in `components.widget_factory`—such as `text_input`, `select`, and `multiselect` (re-exported in `wizard.wizard`)—when creating widgets. They automatically hook into `_update_profile` so that the sidebar, summary, and exports stay in sync.
- Call `state.ensure_state.ensure_state()` early; it now migrates legacy flat keys like `company_name` or `contact_email` into the canonical schema paths (`company.name`, `company.contact_email`) so scraped data prefills the forms.
- After ingestion (via URL, PDF, or text paste), run `coerce_and_fill()` **and** `normalize_profile()` before rendering the form. This ensures consistent casing, whitespace, and de-duplication of lists. The normalizer returns a validated dictionary and will trigger the JSON “repair” fallback only if the cleaned payload would violate the schema.

**DE:**

- Widget-Vorgabewerte immer über `wizard._logic.get_value("<Pfad>")` beziehen. Die Daten in `st.session_state[StateKeys.PROFILE]` sind die einzige Wahrheitsquelle und enthalten bereits Schema-Defaults.
- Verwende Schema-Pfade (z. B. `"company.name"`, `"location.primary_city"`) als Widget-Keys. Binde Eingaben nicht an veraltete `ui.*`-Keys, wenn Daten ausgelesen werden.
- Nutze zum Rendern die Helfer in `components.widget_factory` (`text_input`, `select`, `multiselect`, auch via `wizard.wizard` verfügbar). Diese binden das Widget automatisch an `_update_profile`, sodass Sidebar, Zusammenfassung und Exporte stets synchron bleiben.
- Rufe früh `state.ensure_state.ensure_state()` auf; dort werden Legacy-Schlüssel wie `company_name` oder `contact_email` auf die kanonischen Schema-Pfade (`company.name`, `company.contact_email`) migriert, damit Scrapes die Formulare vorbefüllen.
- Führe nach dem Import (URL, PDF oder Texteingabe) immer `coerce_and_fill()` **und** `normalize_profile()` aus, bevor das Formular gerendert wird. So werden Groß-/Kleinschreibung, Leerzeichen und Duplikate in Listen vereinheitlicht. Der Normalisierer liefert ein valides Dictionary und nutzt die JSON-Reparatur nur, falls das bereinigte Profil sonst gegen das Schema verstoßen würde.

## RecruitingWizard Schema – Single Source of Truth / Master-Schema RecruitingWizard

**EN:** The new RecruitingWizard master schema (see `core/schema.py`) unifies the company, team, role, skills, benefits, interview process, and summary data that power the wizard UI, business logic, and exports. Each field is represented by a typed Pydantic model, and `WIZARD_KEYS_CANONICAL` provides the canonical dot-paths so that other modules (`wizard/`, `question_logic.py`, exports) remain in sync. Source tracking and gap analysis are first-class citizens via `SourceMap` entries (`origin: user|extract|web` with confidence and `source_url`) and `MissingFieldMap` flags that carry field ownership and reminders. Enable this schema by setting `SCHEMA_WIZARD_V1=1` (a feature flag is in place for gradual rollout). When the flag is active, `state.ensure_state.ensure_state()` seeds Streamlit with a `RecruitingWizard` payload, wizard pages surface the new Department/Team sections, and exports rely on `WIZARD_KEYS_CANONICAL`. Legacy payloads are mapped via `WIZARD_ALIASES`, so existing ingestion flows continue to work while the UI migrates to the new structure.

**DE:** Das neue Master-Schema der RecruitingWizard-Anwendung (`core/schema.py`) vereint die Daten zu Unternehmen, Team, Rolle, Skills, Benefits, Interview-Prozess und Zusammenfassung als zentrale Wahrheitsquelle für Wizard, Logik und Exporte. Jedes Feld wird durch ein typisiertes Pydantic-Modell repräsentiert, und `WIZARD_KEYS_CANONICAL` liefert die kanonischen Dot-Pfade, damit UI (`wizard/`), Business-Logik und Exporte identisch bleiben. Source-Tracking und Gap-Analyse sind über `SourceMap`-Einträge (Herkunft: user|extract|web mit Confidence und `source_url`) und `MissingFieldMap`-Markierungen mit Verantwortlichen und Hinweisen direkt unterstützt. Aktiviere das Schema mit `SCHEMA_WIZARD_V1=1` (ein Feature-Flag ermöglicht einen gestaffelten Rollout). Ist das Flag aktiv, initialisiert `state.ensure_state.ensure_state()` den Streamlit-State mit einem `RecruitingWizard`-Payload, die Wizard-Seiten zeigen die neuen Department-/Team-Abschnitte und Exporte stützen sich auf `WIZARD_KEYS_CANONICAL`. Bestehende Payloads bleiben dank `WIZARD_ALIASES` kompatibel, sodass bisherige Import-Pfade weiterlaufen, während die UI auf die neue Struktur umstellt.
