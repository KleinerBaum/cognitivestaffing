# Changelog

## Unreleased

- **EN:** Removed placeholder claim/logo defaults from the sidebar and replaced them with a bilingual "Set branding" call-to-action plus empty defaults in tests.
  **DE:** Platzhalter für Claim und Logo in der Sidebar entfernt – stattdessen erscheint ein zweisprachiger „Branding setzen“-Hinweis, und Tests erwarten nun leere Defaults.
- **EN:** Finalised the wizard navigation: the eight Streamlit pages now follow
  the file order `01_jobad.py` → `08_summary.py`, the deprecated
  `WIZARD_ORDER_V2` / `WIZARD_STEP_ORDER_ENABLED` flags have been removed, and
  navigation now always uses the step-order router after retiring the legacy
  runner.
  **DE:** Wizard-Navigation finalisiert: Die acht Streamlit-Seiten folgen der
  Dateireihenfolge `01_jobad.py` → `08_summary.py`, die veralteten Flags
  `WIZARD_ORDER_V2` / `WIZARD_STEP_ORDER_ENABLED` wurden entfernt und der
  Step-Order-Router ersetzt den Legacy-Lauf vollständig.
- **EN:** Chip multiselects now expose context-aware bilingual hints, guiding
  users when adding skills, benefits, languages, or job-ad sections.
  **DE:** Chip-Multiselects zeigen nun kontextsensible zweisprachige Hinweise
  und führen beim Hinzufügen von Skills, Benefits, Sprachen oder Anzeigeninhalten.
- **EN:** Updated the wizard to drop ACME/example.com placeholders, using
  bilingual helper text and empty schema defaults that mark required fields
  instead of demo values.
  **DE:** Den Wizard von ACME-/example.com-Platzhaltern befreit: Jetzt geben
  zweisprachige Hinweise Orientierung, während leere Schema-Defaults
  Pflichtfelder kennzeichnen statt Demo-Werte zu befüllen.
- **EN:** Unified the schema layer around `NeedAnalysisProfile`: wizard bindings
  and exports now consume the same canonical dot-paths from
  `constants/keys.ProfilePaths`, and the `SCHEMA_WIZARD_V1` rollout flag has
  been retired.
  **DE:** Die Schema-Schicht um `NeedAnalysisProfile` vereinheitlicht: Wizard-
  Bindings und Exporte verwenden dieselben kanonischen Dot-Pfade aus
  `constants/keys.ProfilePaths`, der Rollout-Schalter `SCHEMA_WIZARD_V1` wurde
  abgeschafft.
- **EN:** Prevent ESCO placeholder URIs from contacting the live API by serving
  cached essential skills whenever offline fixtures include the identifier.
  **DE:** Verhindert, dass ESCO-Platzhalter-URIs die Live-API erreichen, indem
  gespeicherte Kernkompetenzen genutzt werden, sobald Offline-Fixdaten die
  Kennung enthalten.
- **EN:** Refreshed README, developer guide, key registry, and JSON pipeline
  docs to describe the unified schema, current field names, and the latest
  wizard flow in English and German.
  **DE:** README, Developer-Guide, Key-Registry und JSON-Pipeline-Doku
  überarbeitet – mit einheitlichem Schema, aktuellen Feldnamen und dem
  neuesten Wizard-Fluss auf Deutsch und Englisch.
- **EN:** Documented the repository folder structure so maintainers can map
  modules like `pages/`, `wizard/`, and `core/` at a glance.
  **DE:** Die Projektordner dokumentiert, damit Maintainer:innen Verzeichnisse
  wie `pages/`, `wizard/` und `core/` auf einen Blick zuordnen können.
- **EN:** Refined the Summary step with a dedicated "Create a job ad" section featuring a compact field selector, collapsible preferences, and kept manual additions next to the generation controls while relocating the internal-process review to the Process step.
  **DE:** Den Summary-Schritt überarbeitet: Eigener Bereich „Stellenanzeige erstellen“ mit kompakter Feldauswahl und einklappbaren Präferenzen, manuelle Ergänzungen beim Generator belassen und die Übersicht „Interne Prozesse definieren“ in den Prozess-Schritt verschoben.

- **EN:** Routed company web enrichment through `_update_profile` so “Get Info from Web” immediately mirrors updates across sidebar and form inputs.
  **DE:** Unternehmens-Webanreicherungen laufen nun über `_update_profile`, damit „Infos aus dem Web holen“ Änderungen sofort in Sidebar und Formular widerspiegelt.
- **EN:** Replaced unsupported `format: "uri"` markers in the Need Analysis schema with URL patterns, added a whitelist-based sanitizer before Responses API calls, and kept the persisted schema in lockstep.
  **DE:** Nicht unterstützte `format: "uri"`-Marker im Need-Analysis-Schema durch URL-Pattern ersetzt, einen Whitelist-Sanitizer vor Responses-Aufrufen ergänzt und das persistierte Schema synchronisiert.
- **EN:** Introduced the Aurora Fjord palette across both themes and the skill board, blending midnight blues with glacial aqua and ember accents to steady hierarchy and boost contrast.
  **DE:** Die Aurora-Fjord-Palette in beiden Themes und dem Skill-Board eingebracht – Mitternachtsblau, Gletscher-Aqua und Amber-Akzente stabilisieren die Hierarchie und verbessern den Kontrast.
- **EN:** Enforced an 88% coverage floor in CI, uploaded coverage HTML/XML artifacts, and defaulted `llm`-tagged tests to opt-in mode so heuristics stay guarded without blocking offline contributors.
  **DE:** In der CI gilt jetzt eine Abdeckungsuntergrenze von 88 %, Coverage-HTML/XML-Artefakte werden hochgeladen und `llm`-markierte Tests bleiben optional, sodass Heuristiken geschützt werden, ohne Offline-Contributor:innen auszubremsen.
- **EN:** Prevented Streamlit duplicate-key crashes for branding uploads by namespacing the sidebar uploader and persisting assets via safe callbacks.
  **DE:** Streamlit-Abstürze durch doppelte Branding-Upload-Keys verhindert, indem der Sidebar-Uploader einen eigenen Namespace erhält und Assets über sichere Callbacks gespeichert werden.
- **EN:** Migrated legacy session keys such as `company_name` and `contact_email` to the canonical wizard schema paths so scraped profiles prefill the company/contact forms, and aligned the widget factories with the default `get_value`/`_update_profile` callbacks.
  **DE:** Legacy-Session-Keys wie `company_name` und `contact_email` werden nun auf die kanonischen Wizard-Schema-Pfade gemappt, sodass Scrapes die Unternehmens- und Kontakt-Formulare vorbefüllen; die Widget-Factories nutzen dabei standardmäßig das `get_value`/`_update_profile`-Callback-Muster.
- **EN:** Improved Rheinbahn ingestion heuristics: detect "suchen wir in …" cities, route benefit keywords to `company.benefits`, and parse footer contacts with confidence metadata.
  **DE:** Rheinbahn-Heuristiken verbessert: Städte aus "suchen wir in …" erkennen, Benefit-Schlagworte nach `company.benefits` mappen und Footer-Kontakte inklusive Vertrauensmetadaten parsen.
- **EN:** Ensured the Poetry dependency set requires `openai>=1.99.3` so the Responses API tooling matches the pip requirements.
  **DE:** Poetry-Abhängigkeiten verlangen nun `openai>=1.99.3`, damit das Responses-API-Tooling mit den pip-Requirements übereinstimmt.
- **EN:** Hardened optional profile URL sanitisation so canonicalisation and wizard updates trim blanks to `None`, preventing schema resets.
  **DE:** Optionale Profil-URLs weiter gehärtet: Kanonisierung und Wizard-Updates kürzen leere Werte jetzt auf `None`, sodass keine Schema-Resets mehr ausgelöst werden.
- **EN:** Downgraded rule-matcher logs when phone or country values are absent so optional contact fields no longer emit warning-level noise.
  **DE:** Log-Ausgabe des Regelabgleichs herabgestuft, wenn Telefon- oder Länderdaten fehlen, sodass optionale Kontaktfelder keine Warnungen mehr erzeugen.
- **EN:** Rerouted lightweight tasks to `gpt-4.1-mini` and escalated reasoning-heavy flows to `o4-mini`, cascading through `o3` and `gpt-4o` automatically; environment overrides now normalise to these tiers.
  **DE:** Leichte Aufgaben laufen nun auf `gpt-4.1-mini`, während Zusammenfassungen und Erklärungen automatisch auf `o4-mini` (mit Fallbacks über `o3` und `gpt-4o`) eskalieren; Umgebungs-Overrides werden auf diese Stufen normalisiert.
- **EN:** Resolved duplicate Streamlit widget keys for branding uploads by giving the legacy wizard uploader its own identifier and clearing both caches together.
  **DE:** Doppelte Streamlit-Widget-Keys beim Branding-Upload behoben, indem der Legacy-Wizard einen eigenen Schlüssel erhält und beide Caches gemeinsam geleert werden.
- **EN:** Consolidated dependency management so `requirements.txt` is the deployment source of truth and Streamlit no longer detects competing requirement files.
  **DE:** Abhängigkeitsverwaltung konsolidiert, sodass `requirements.txt` als Deployment-Quelle dient und Streamlit keine konkurrierenden Requirements-Dateien mehr meldet.
- **EN:** Slimmed the default requirement set to core app dependencies and exposed optional OCR/spaCy extras via `requirements-optional.txt` for contributors who need advanced ingestion features.
  **DE:** Die Standard-Requirements auf zentrale App-Abhängigkeiten verschlankt und optionale OCR-/spaCy-Erweiterungen über `requirements-optional.txt` verfügbar gemacht, damit Contributor:innen bei Bedarf die erweiterten Ingestion-Funktionen aktivieren können.
- **EN:** Added `PyMuPDF` to the primary dependency list so PDF exports for interview guides run on fresh environments without manual installs.
  **DE:** `PyMuPDF` zur primären Abhängigkeitsliste hinzugefügt, damit PDF-Exporte der Interview-Guides in neuen Umgebungen ohne manuelle Installation funktionieren.
- **EN:** Removed the unused `configloader` and `tenacity` dependencies from `requirements.txt` to keep deployments leaner.
  **DE:** Die ungenutzten Abhängigkeiten `configloader` und `tenacity` aus `requirements.txt` entfernt, um Deployments schlanker zu halten.
- **EN:** Updated the skill market fallback caption to explain that benchmarks are missing and encourage capturing skill data instead of showing neutral placeholder numbers.
  **DE:** Die Skill-Markt-Fallback-Beschriftung angepasst: Sie erklärt nun das Fehlen von Benchmarks und fordert zum Erfassen von Skill-Daten auf, statt neutrale Platzhalterzahlen darzustellen.
- **EN:** Moved the sidebar “Benefit ideas” module into the Rewards & Benefits step and positioned the step summary directly above each wizard header.
  **DE:** Das Sidebar-Modul „Benefit-Ideen“ in den Schritt „Leistungen & Benefits“ verschoben und die Schrittübersicht direkt über jede Wizard-Überschrift gesetzt.
- **EN:** Simplified the Summary step layout by dropping the Key highlights block and moving the JSON export button to the bottom for clearer final actions.
  **DE:** Das Layout des Zusammenfassungs-Schritts vereinfacht: Der Block „Wesentliche Eckdaten“ entfällt und der JSON-Export-Button steht jetzt unten für klarere Abschlussaktionen.
- **EN:** Added regression tests for phone number and website URL normalisation to guard the wizard’s new validation paths.
  **DE:** Regressions-Tests für die Normalisierung von Telefonnummern und Website-URLs ergänzt, um die neuen Validierungspfade des Wizards zu schützen.

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
- **EN:** Enabling `SCHEMA_WIZARD_V1` booted the UI on the RecruitingWizard schema: session state stored the new Company/Department/Team payload, wizard pages highlighted the canonical fields, and exports read `WIZARD_KEYS_CANONICAL` with alias-backed fallbacks (flag removed in v1.2.0).
  **DE:** Mit aktiviertem `SCHEMA_WIZARD_V1` arbeitete die Oberfläche vollständig auf dem RecruitingWizard-Schema: Der Session-State speicherte die neuen Company-/Department-/Team-Daten, die Wizard-Seiten zeigten die kanonischen Felder und Exporte nutzten `WIZARD_KEYS_CANONICAL` mit Alias-Fallbacks (Flag seit v1.2.0 entfernt).
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
