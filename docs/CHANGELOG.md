# Changelog

## Unreleased

- **EN:** Rerouted lightweight tasks to `gpt-4o-mini` (GPT-4.1-nano) while keeping summarisation/explanation flows on `gpt-5-nano` (`gpt-5.1-nano` endpoint); environment overrides now normalise to these tiers.
  **DE:** Leichte Aufgaben laufen nun auf `gpt-4o-mini` (GPT-4.1-nano), während Zusammenfassungen und Erklärungen weiterhin `gpt-5-nano` (Endpoint `gpt-5.1-nano`) nutzen; Umgebungs-Overrides werden auf diese Stufen normalisiert.
- **EN:** Resolved duplicate Streamlit widget keys for branding uploads by giving the legacy wizard uploader its own identifier and clearing both caches together.
  **DE:** Doppelte Streamlit-Widget-Keys beim Branding-Upload behoben, indem der Legacy-Wizard einen eigenen Schlüssel erhält und beide Caches gemeinsam geleert werden.

## v1.1.0 – Wizard Hardening & Schema Alignment / Wizard-Härtung & Schemaabgleich (2025-11-19)

- **EN:** Harmonised WizardRouter navigation so `?step` stays in sync, every step change scrolls to the top, optional skips count as completed, and first-incomplete jumps reuse the new back helper and regression tests.
  **DE:** WizardRouter-Navigation synchronisiert nun `?step`, löst bei jedem Schrittwechsel einen Scroll-to-Top aus, markiert optionale Skips als erledigt und nutzt den neuen Zurück-Helfer plus Regressionstests für First-Incomplete-Sprünge.
- **EN:** Normalise wizard widget defaults via `_ensure_widget_state()` so inputs seed before rendering and Streamlit no longer raises "Cannot set widget" exceptions.
  **DE:** Normalisiert die Widget-Defaults im Wizard über `_ensure_widget_state()`, damit Eingaben vor dem Rendern initialisiert werden und Streamlit keine "Cannot set widget"-Ausnahmen mehr auslöst.
- **EN:** Normalised company contact phone numbers and websites across the wizard, cleaning noisy values and storing cleared fields as `None` for consistent profile state.
  **DE:** Unternehmens-Telefonnummern und Websites im Wizard normalisiert, Störzeichen entfernt und geleerte Felder als `None` im Profil hinterlegt, um den Zustand konsistent zu halten.
- **EN:** Hardened skill/benefit suggestion fallbacks to auto-switch from the Responses API to the legacy chat backend or static shortlists when outages occur; `USE_RESPONSES_API` now coordinates with `USE_CLASSIC_API` so administrators can force either pipeline explicitly.
  **DE:** Skill- und Benefit-Vorschläge nutzen bei Ausfällen automatisch die Chat-Completions-API oder statische Shortlists; `USE_RESPONSES_API` koordiniert mit `USE_CLASSIC_API`, sodass Administrator:innen gezielt einen der Pfade erzwingen können.
- **EN:** Gated all AI suggestion buttons and document generations behind the OpenAI API key; the UI now shows a lock message instead of firing requests when the key is missing.
  **DE:** Sperrt sämtliche KI-Vorschläge und Dokumentgenerierungen, solange kein OpenAI-API-Schlüssel vorliegt, und blendet statt API-Aufrufen einen Hinweis mit Schloss-Symbol ein.
- **EN:** Unified Responses API retry handling logs warnings and triggers chat/static fallbacks whenever calls fail or return invalid JSON payloads.
  **DE:** Vereinheitlichte Responses-Retry-Logik protokolliert Warnungen und aktiviert Chat-/statische Fallbacks, sobald Aufrufe scheitern oder ungültiges JSON liefern.
- **EN:** Moved the remaining legacy wizard helpers into the modular package, exposing `_update_profile` and autofill rendering without dynamic imports for clearer navigation.
  **DE:** Verbleibende Wizard-Helfer wurden in das modulare Paket verlagert; `_update_profile` und die Autofill-Darstellung stehen nun ohne dynamische Importe für bessere Übersicht zur Verfügung.
- **EN:** Extended branding integration with sidebar overrides—logo uploads, colour pickers, and claim edits now feed exports, while job ads and fallbacks mention the slogan and brand colour by default.
  **DE:** Branding-Integration ausgebaut: Sidebar-Overrides für Logo, Farbe und Claim fließen in Exporte ein; Stellenanzeigen und Fallbacks referenzieren Claim und Markenfarbe automatisch.
- **EN:** Enabling `SCHEMA_WIZARD_V1` now boots the UI on the RecruitingWizard schema: session state stores the new Company/Department/Team payload, wizard pages highlight the canonical fields, and exports read `WIZARD_KEYS_CANONICAL` with alias-backed fallbacks.
  **DE:** Mit aktiviertem `SCHEMA_WIZARD_V1` arbeitet die Oberfläche jetzt vollständig auf dem RecruitingWizard-Schema: Der Session-State speichert die neuen Company-/Department-/Team-Daten, die Wizard-Seiten zeigen die kanonischen Felder und Exporte nutzen `WIZARD_KEYS_CANONICAL` mit Alias-Fallbacks.
- **EN:** Enforced full NeedAnalysisProfile ↔ wizard alignment by enumerating every schema path in `ProfilePaths`, surfacing them on wizard pages, and verifying coverage via automated tests.
  **DE:** Vollständige NeedAnalysisProfile↔Wizard-Ausrichtung umgesetzt, indem sämtliche Schema-Pfade in `ProfilePaths` erfasst, in den Wizard-Seiten angezeigt und per automatisierten Tests abgesichert werden.
- **EN:** Improved the salary expectation sidebar: it now surfaces the last estimate with its fallback/source label, visualises factor impacts with Plotly, and reuses the static benefit shortlist whenever the AI call returns no items.
  **DE:** Salary-Sidebar verbessert: Zeigt die letzte Schätzung inklusive Fallback-/Quellenhinweis, visualisiert Einflussfaktoren mit Plotly und nutzt die statische Benefit-Shortlist, sobald der KI-Aufruf keine Einträge liefert.

## v1.0.1 – Setup & Branding Refresh / Setup- & Branding-Update (2025-11-05)

### Added / Neu
- **EN:** Branding parser now enriches profiles with `company.logo_url`, `company.brand_color`, and `company.claim`, wiring the logo and claim into the sidebar hero and exports.
  **DE:** Der Branding-Parser ergänzt Profile um `company.logo_url`, `company.brand_color` und `company.claim`, sodass Logo und Claim in Sidebar und Exporten erscheinen.
- **EN:** Documented OpenAI configuration pathways (environment variables, Streamlit secrets, EU base URL) including in-app warnings when the key is missing.
  **DE:** OpenAI-Konfigurationswege (Umgebungsvariablen, Streamlit-Secrets, EU-Basis-URL) dokumentiert – inklusive In-App-Warnung, falls der Schlüssel fehlt.
- **EN:** Added contributor guidance for the normalization pipeline, feature flags, and `ProfilePaths` widget bindings in README and developer docs.
  **DE:** Entwicklerleitfaden für Normalisierungspipeline, Feature-Flags und `ProfilePaths`-Widget-Bindungen in README und Doku ergänzt.

### Fixed / Behoben
- **EN:** Resolved the Company step autofill crash caused by branding assets missing dominant colours.
  **DE:** Absturz der Unternehmens-Autofill-Logik behoben, wenn Branding-Assets keine dominanten Farben lieferten.
- **EN:** Hardened structured extraction payload handling to recover gracefully from invalid JSON envelopes.
  **DE:** Verarbeitung der strukturierten Extraktions-Payload gehärtet, sodass ungültige JSON-Hüllen sauber abgefangen werden.
- **EN:** Fixed media uploads that previously failed when file names contained non-ASCII characters.
  **DE:** Fehler bei Medien-Uploads korrigiert, wenn Dateinamen Nicht-ASCII-Zeichen enthielten.

### Refactored / Refaktoriert
- **EN:** Unified schema keys via `constants.keys.ProfilePaths` across wizard steps, state synchronisation, and exports (CS_SCHEMA_PROPAGATE).
  **DE:** Schema-Keys über `constants.keys.ProfilePaths` zwischen Wizard, State-Sync und Exporten vereinheitlicht (CS_SCHEMA_PROPAGATE).

### Docs / Doku
- **EN:** README now highlights feature flags, Poppler/Tesseract prerequisites, and the extraction → normalisation pipeline.
  **DE:** README weist nun auf Feature-Flags, Poppler/Tesseract-Voraussetzungen und die Extraktions-→-Normalisierungspipeline hin.
- **EN:** Added developer snippets for creating wizard fields and extending rule-based extraction.
  **DE:** Entwickler-Snippets für neue Wizard-Felder und die Erweiterung regelbasierter Extraktion ergänzt.

## v1.0.0 – Wizard-Vollmodernisierung & KI-Assistenten (2025-10-27)

- feat: standardise wizard layout, schema keys, and export mapping across all steps (CS_SCHEMA_PROPAGATE)
  - Feature: Wizard-Layout, Schema-Keys und Export-Mapping für alle Schritte vereinheitlicht (CS_SCHEMA_PROPAGATE)
- feat: add pragmatic/formal/casual intro captions (EN/DE) to every step via `panel_intro_variants`
  - Feature: Pragmatische, formelle und lockere Intro-Captions (DE/EN) für jeden Schritt über `panel_intro_variants`
- feat: expand AI helpers with refreshed skill/benefit/responsibility suggestions and interview guide generation
  - Feature: KI-Helfer für Skills, Benefits, Verantwortlichkeiten und Interview-Guides erweitert
- refactor: extract reusable wizard components for suggestion chips, inputs, and state sync
  - Refactor: Wiederverwendbare Wizard-Komponenten für Suggestion-Chips, Eingaben und State-Sync extrahiert
- feat: streamline navigation UX with top-of-step focus, responsive layout, and mobile stacking
  - Feature: Navigations-UX mit Top-of-Step-Fokus, responsivem Layout und Mobile-Stacking optimiert
- fix: correct invalid city fallbacks and reassign flexible hours to employment work schedule (CS_SCHEMA_PROPAGATE)
  - Fix: Ungültige Städtewerte korrigiert und flexible Arbeitszeiten dem Arbeitszeitplan zugeordnet (CS_SCHEMA_PROPAGATE)
- fix: gate AI suggestions behind explicit user triggers and reset caches on refresh
  - Fix: KI-Vorschläge nur nach aktiver Auslösung und Cache-Reset bei Aktualisierung
- fix: cover outstanding wizard regression tests for skill board, legacy state, and error banners
  - Fix: Ausstehende Wizard-Regressionstests für Skill-Board, Legacy-State und Fehlermeldungen abgedeckt
- docs: capture unified design tokens, hover/focus styling, and mobile accessibility guidance
  - Dokumentation: Einheitliche Design-Tokens, Hover/Fokus-Styling und mobile Accessibility-Anleitung dokumentiert
- chore: align linting, mypy checks, and deployment requirements for the release train
  - Chore: Linting-, mypy-Prüfungen und Deployment-Requirements für den Release-Train abgestimmt
- docs: update README and changelog, bump version identifiers to 1.0.0, and confirm release readiness
  - Dokumentation: README und Changelog aktualisiert, Versionsnummern auf 1.0.0 gesetzt und Release-Bereitschaft bestätigt

## v0.5 – GPT-5-Updates und RAG-Support (2025-02-18)
- docs: refresh README, agent catalog, and telemetry guides with bilingual RAG + gap-analysis instructions (EN/DE)
  - Dokumentation: aktualisiert README, Agenten-Übersicht und Telemetrie-Leitfaden mit zweisprachigen RAG- und Gap-Analyse-Hinweisen (DE/EN)
- fix: delay critical location city gating to later wizard sections so early validation only flags the company country (EN/DE)
  - Fix: verschiebt die kritische Prüfung der Stadt auf spätere Wizard-Abschnitte, damit zu Beginn nur das Unternehmensland verlangt wird (DE/EN)
- feat: auto-describe extraction tools with highlighted schema fields while keeping custom overrides for salary and other agents (EN/DE)
  - Feature: beschreibt Extraktions-Tools automatisch mit hervorgehobenen Schemafeldern und erlaubt weiter maßgeschneiderte Texte für Gehalts- oder andere Agenten (DE/EN)
- refactor: rename structured extraction handles to `NeedAnalysisProfile` and salary responses to `SalaryExpectationResponse` for consistent schema naming (EN/DE)
  - Refactor: vereinheitlicht die Funktionsnamen für strukturierte Extraktion auf `NeedAnalysisProfile` bzw. `SalaryExpectationResponse`, damit sie den Schemanamen entsprechen (DE/EN)

- feat: switch RAG embeddings to `text-embedding-3-large` (3,072-dim) and add `cli/rebuild_vector_store.py` to re-embed existing OpenAI stores (EN/DE)
  - Run `python -m cli.rebuild_vector_store <source_store_id>` and point `VECTOR_STORE_ID` to the printed target once validation passes.
  - Feature: stellt RAG-Embeddings auf `text-embedding-3-large` (3.072 Dimensionen) um und liefert `cli/rebuild_vector_store.py` zum Neu-Einbetten bestehender OpenAI-Stores (DE/EN)
  - Nach dem Lauf von `python -m cli.rebuild_vector_store <source_store_id>` die neue Store-ID in `VECTOR_STORE_ID` übernehmen.
- feat: allow opting into classic Chat Completions via `USE_CLASSIC_API` while keeping Responses as the default (EN/DE)
  - Feature: erlaubt über `USE_CLASSIC_API` den Wechsel zur klassischen Chat-Completions-API, während Responses der Standard bleibt (DE/EN)
- chore: raise OpenAI SDK minimum to 1.99.3 to stay compatible with updated Responses stream events (EN/DE)
  - Chore: hebt die Mindestversion des OpenAI-SDKs auf 1.99.3 an, um mit den aktualisierten Responses-Streaming-Ereignissen kompatibel zu bleiben (DE/EN)
- feat: re-enable ESCO occupation + essential skill seeding in follow-up question logic (EN)
  - Feature: reaktiviert ESCO-Beruf- und Kernkompetenz-Vorschläge in der Follow-up-Logik (DE)
- chore: consolidate dependency management under `requirements.txt` and drop setup-based installs (EN/DE)
  - Chore: bündelt die Abhängigkeitsverwaltung in `requirements.txt` und entfernt setup-basierte Installationen (DE/EN)
- fix: pin `streamlit-sortables` to 0.3.1 to restore deployment compatibility (EN)
  - Fix: setzt `streamlit-sortables` auf Version 0.3.1 fest, um die Bereitstellung wiederherzustellen (DE)
- docs: document the content cost router, GPT-4/GPT-3.5 fallback flow, and model override toggle (EN/DE)
  - Dokumentation: beschreibt den Content-Kostenrouter, den GPT-4/GPT-3.5-Fallback-Flow und den Modell-Override-Umschalter (DE/EN)
