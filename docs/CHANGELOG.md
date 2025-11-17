# Changelog

## Unreleased

- **EN:** Refined the salary sidebar so estimates focus on the job title, core responsibilities, must-have and nice-to-have requirements, tools/tech/certificates, language expectations, industry, and city hints; the Streamlit navigation no longer exposes the redundant overview entry.
  **DE:** Die Gehaltsschätzung nutzt jetzt Jobtitel, Kernaufgaben, Muss- und Nice-to-have-Anforderungen, Tools/Technologien/Zertifikate, Sprachvorgaben, Branche sowie Stadthinweise als Basis und blendet den überflüssigen Überblick-Link aus der Streamlit-Navigation aus.
- **EN:** Replaced every `use_container_width` flag with the new
  `width` argument across Streamlit widgets to remove the 2025
  deprecation warning while keeping the stretch layout intact.
  **DE:** Sämtliche `use_container_width`-Schalter auf das neue
  `width`-Argument der Streamlit-Widgets umgestellt, damit die
  angekündigte Deprecation-Warnung für 2025 entfällt und das
  Stretch-Layout erhalten bleibt.
- **EN:** Added a Quick vs Precise toggle in the settings sidebar that maps to `gpt-4.1-mini`/minimal reasoning or `o4-mini`/high reasoning, reuses cached structured extractions, and parallelises vector-store lookups for faster responses.
  **DE:** Einen Schnell-/Präzisionsmodus in der Seitenleiste ergänzt, der zwischen `gpt-4.1-mini` mit minimalem Denkaufwand und `o4-mini` mit hohem Denkaufwand umschaltet, strukturierte Extraktionen cached und Vector-Store-Abfragen parallelisiert.
- **EN:** Closed the Interview Guide Responses schema by enforcing
  `additionalProperties: false` on every object level and adding a
  regression test so OpenAI no longer rejects the format.
  **DE:** Das Interview-Guide-Responses-Schema abgedichtet, indem
  `additionalProperties: false` auf allen Objekt-Ebenen erzwungen und
  ein Regressionstest ergänzt wurde, sodass OpenAI das Format wieder
  akzeptiert.
- **EN:** Renamed all OpenAI helper parameters from `max_tokens` to
  `max_completion_tokens` so every Responses and Chat call uses the
  official field name and avoids unsupported-parameter warnings on the
  latest models.
  **DE:** Sämtliche OpenAI-Helfer von `max_tokens` auf
  `max_completion_tokens` umgestellt, damit alle Responses- und
  Chat-Aufrufe den offiziellen Feldnamen nutzen und neue Modelle keine
  Warnungen wegen nicht unterstützter Parameter mehr ausgeben.
- **EN:** Added a dedicated "Q&A" wizard step that surfaces generated follow-up questions right after extraction, complete with interactive input widgets to capture SME responses inline.
  **DE:** Einen eigenen "Q&A"-Wizard-Schritt ergänzt, der die generierten Anschlussfragen direkt nach der Extraktion bündelt und mit interaktiven Eingabefeldern für unmittelbares Eintragen der SME-Antworten versieht.
- **EN:** Hardened benefit suggestions by cascading through the legacy Chat backend before falling back to the static shortlist when Responses output is missing or malformed.
  **DE:** Benefit-Vorschläge robuster gemacht, indem vor der statischen Shortlist zuerst der Legacy-Chat-Backend-Aufruf versucht wird, falls die Responses-Antwort fehlt oder fehlerhaft ist.
- **EN:** Retired the last Wizard v1 scaffolding – removed the unused
  `wizard_state['feature']` bootstrap and the deprecated
  `core.schema` aliases/`coerce_and_fill_wizard` helper now that the
  `SCHEMA_WIZARD_V1` flag is gone for good, and added a regression test
  that fails if those legacy strings reappear in Python sources.
  **DE:** Letzte Wizard-v1-Stützen entfernt – der ungenutzte
  `wizard_state['feature']`-Bootstrap sowie die veralteten
  `core.schema`-Aliasse bzw. der `coerce_and_fill_wizard`-Helper sind nach dem
  endgültigen Aus für `SCHEMA_WIZARD_V1` gelöscht; zusätzlich prüft ein
  Regressionstest, dass diese Legacy-Strings nicht zurückkehren.
- **EN:** Integrated LangChain’s `StructuredOutputParser` and `PydanticOutputParser` into the extraction stack so prompts ship
  with generated format instructions and responses deserialize straight into `NeedAnalysisProfile` without manual JSON plumbing.
  **DE:** LangChains `StructuredOutputParser` und `PydanticOutputParser` im Extraktions-Stack verankert, sodass Prompts
  automatische Format-Hinweise erhalten und Antworten ohne manuelle JSON-Nachbearbeitung direkt in `NeedAnalysisProfile`
  einfließen.
- **EN:** Polished the Streamlit experience with a branded hero banner, a
  three-tab summary layout (Profile overview, Insights, Export), an interactive
  Plotly salary visualisation, and an ESCO skill explorer that caches
  descriptions for fast lookups.
  **DE:** Die Streamlit-Erfahrung mit gebrandetem Hero-Banner, dreigeteilter
  Zusammenfassung („Profilübersicht“, „Insights“, „Export“), interaktiver
  Plotly-Gehaltssicht und einem ESCO-Skill-Explorer mit gecachten
  Beschreibungen verfeinert.
- **EN:** Added dedicated `department.*` and `team.*` profile sections, a
  customer-contact flag for `position.*`, and requirement toggles for
  background, reference, and portfolio checks. Step 3 (Team & Context) now
  binds these fields end-to-end, the follow-up logic validates them as critical
  before advancing, and the schema propagation script refreshes generated
  components.
  **DE:** Eigene `department.*`- und `team.*`-Profilebenen ergänzt, einen
  Kundenkontakt-Schalter für `position.*` eingeführt und Anforderungs-Toggles
  für Background-, Referenz- und Portfolio-Prüfungen hinzugefügt. Schritt 3
  („Team & Kontext“) bindet die Felder durchgängig ein, die Folgefragen-Logik
  behandelt sie vor dem Weiterklicken als kritisch und das Schema-Propagation-
  Skript aktualisiert die generierten Komponenten.
- **EN:** Rebuilt the onboarding entry experience with a five-line bilingual
  briefing on OpenAI/ESCO-powered intake, centred URL/upload inputs of equal
  width, retired the manual text area, and swapped the green gradient CTA for a
  compact continue control.
  **DE:** Das Onboarding neu inszeniert: Fünf zweisprachige Briefing-Zeilen zu
  OpenAI-/ESCO-gestützter Intake, mittig ausgerichtete URL-/Upload-Felder in
  gleicher Breite, das manuelle Textfeld entfernt und den grünen
  Gradient-CTA durch einen kompakten Weiter-Button ersetzt.
- **EN:** The onboarding URL/upload fields and continue button stay disabled
  (with a bilingual hint) until an OpenAI API key unlocks LLM ingestion, so
  users cannot trigger uploads while AI features are offline.
  **DE:** Onboarding-URL-/Upload-Felder sowie der Weiter-Button bleiben (mit
  zweisprachigem Hinweis) deaktiviert, bis ein OpenAI-API-Schlüssel die
  LLM-Intake freischaltet – dadurch lassen sich keine Uploads starten, wenn die
  KI-Funktionen offline sind.
- **EN:** Rolled out a tabbed extraction review in step 1 with editable company,
  role, logistics, requirements, and process tabs, added an interactive
  completion tracker across all eight steps, modernised follow-up questions with
  chip suggestions and field-aware widgets, and derived the brand colour from
  uploaded logos to auto-fill `company.brand_color`.
  **DE:** Eine tabbasierte Extraktionsübersicht im ersten Schritt eingeführt,
  in der Unternehmens-, Rollen-, Logistik-, Anforderungs- und Prozessdaten
  sofort bearbeitbar sind; ein interaktiver Fortschrittstracker über alle acht
  Schritte zeigt den Erfüllungsgrad, Anschlussfragen nutzen Chip-Vorschläge und
  feldspezifische Widgets und hochgeladene Logos liefern automatisch die
  Markenfarbe für `company.brand_color`.


- **EN:** Streamlined the sidebar by removing page navigation links, stacking the dark-mode and language switches vertically with flag icons, and triggering salary estimates automatically once job title plus a location hint are available; the panel now lists required fields, summarises the top five drivers in one sentence, and exposes the raw calculation data.
  **DE:** Die Sidebar wurde verschlankt: Seiten-Links entfernt, Dark-Mode- und Sprachumschalter untereinander mit Flaggen-Icons angeordnet und Gehaltsschätzungen starten automatisch, sobald Jobtitel und ein Standorthinweis vorliegen; die Ansicht zeigt die benötigten Felder, fasst die fünf wichtigsten Faktoren in einem Satz zusammen und blendet die Berechnungsdaten sichtbar ein.
- **EN:** Removed the legacy `wizard.layout` widget helpers; the widget factory now wires Streamlit inputs directly to `_update_profile` and exposes the bindings via `wizard.wizard`.
  **DE:** Die veralteten `wizard.layout`-Widget-Helfer entfernt; die Widget-Factory verbindet Streamlit-Inputs jetzt direkt mit `_update_profile` und stellt die Bindings über `wizard.wizard` bereit.
- **EN:** Introduced the `RESPONSES_ALLOW_TOOLS` feature flag: tool payloads stay disabled on Responses by default for the 2025 rollout, while the client automatically falls back to the chat backend whenever tools are required unless the flag is set to `1`.
  **DE:** Das Feature-Flag `RESPONSES_ALLOW_TOOLS` ergänzt: Tool-Payloads bleiben für den Responses-Rollout 2025 standardmäßig deaktiviert, und der Client wechselt automatisch auf das Chat-Backend, sobald Tools benötigt werden – außer das Flag steht auf `1`.
- **EN:** Switched the `Requirements` certificate synchronisation validator to
  the instance-based Pydantic v2 style, silencing deprecation warnings during
  tests and preparing the model for Pydantic 3.
  **DE:** Den Validator zur Synchronisierung der Zertifikatslisten in
  `Requirements` auf die instanzbasierte Pydantic-v2-Schreibweise umgestellt,
  sodass die Deprecation-Warnung in den Tests entfällt und wir für Pydantic 3
  vorbereitet sind.
- **EN:** Normalised legacy helpers to snake_case and added missing return/argument
  type hints across wizard prompts, keeping linting strictness aligned with the
  repository-wide PEP 8 typing expectations.
  **DE:** Legacy-Helfer auf snake_case umgestellt und fehlende Rückgabe- bzw.
  Argument-Typannotationen in Wizard-Prompts ergänzt, damit die strengen
  PEP-8-/Typing-Vorgaben des Repos konsistent bleiben.
- **EN:** Expanded smoke and unit tests for the wizard agent tools (graph,
  knowledge, vacancy, safety) and page metadata to close coverage gaps and guard
  fallback behaviours.
  **DE:** Smoke- und Unit-Tests für die Wizard-Agent-Tools (Graph, Knowledge,
  Vacancy, Safety) sowie die Seiten-Metadaten erweitert, um Abdeckungs­lücken zu
  schließen und Fallback-Verhalten abzusichern.
- **EN:** Locked all OpenTelemetry packages to version 1.26.0, updated
  `requirements.txt` with the optional ingestion libraries, and refreshed
  `artifacts/pip.freeze.txt` so deployments use a consistent stack.
  **DE:** Alle OpenTelemetry-Pakete auf Version 1.26.0 fixiert,
  `requirements.txt` um die optionalen Ingestion-Bibliotheken ergänzt und
  `artifacts/pip.freeze.txt` aktualisiert, damit Deployments auf einem
  konsistenten Stack laufen.
- **EN:** Excised the deprecated `wizard._legacy` runner and scrubbed remaining
  references so the Streamlit wizard always boots through `WizardRouter`.
  **DE:** Den veralteten `wizard._legacy`-Runner vollständig entfernt und alle
  Restverweise bereinigt, sodass der Streamlit-Wizard konsequent über den
  `WizardRouter` startet.
- **EN:** Removed the `sidebar.*` mypy ignore, introduced explicit type aliases, and tightened colour helpers so the sidebar module now passes static checks without suppressions.
  **DE:** Das `sidebar.*`-Mypy-Ignorieren entfernt, explizite Type-Aliases ergänzt und die Farbhelfer präzisiert, sodass das Sidebar-Modul jetzt ohne Unterdrückungen die statischen Prüfungen besteht.
- **EN:** Documented focused pytest loops in the developer guide, covering scoped
  modules, keyword filters, and marking known failures while expectations catch
  intentional behaviour changes.
  **DE:** Fokussierte Pytest-Schleifen im Developer-Guide dokumentiert – mit
  Hinweisen zu Modul-Läufen, Stichwortfiltern sowie XFAIL-Markierungen und
  aktualisierten Erwartungen bei absichtlichen Verhaltensänderungen.
- **EN:** Tuned the Mypy configuration to skip heavy third-party imports (`streamlit`, `requests`, `bs4`) while enforcing `disallow_untyped_defs` on wizard helpers so incremental cleanup can start without regressing strictness on new code.
  **DE:** Die Mypy-Konfiguration angepasst: Umfangreiche Drittanbieter-Imports (`streamlit`, `requests`, `bs4`) werden per `follow_imports = "skip"` ausgelassen, während Wizard-Hilfen `disallow_untyped_defs` erzwingen, damit Aufräumarbeiten schrittweise starten können, ohne neue Lockerungen zu riskieren.
- **EN:** Documented the baseline Mypy failures, added temporary ignore overrides for legacy modules, and published the checklist in `docs/mypy_typing_status.md` to guide future cleanups.
  **DE:** Bestehende Mypy-Fehler dokumentiert, temporäre Ignore-Overrides für Legacy-Module ergänzt und die Checkliste in `docs/mypy_typing_status.md` festgehalten, um kommende Aufräumarbeiten zu steuern.
- **EN:** Removed placeholder claim/logo defaults from the sidebar and replaced them with a bilingual "Set branding" call-to-action plus empty defaults in tests.
  **DE:** Platzhalter für Claim und Logo in der Sidebar entfernt – stattdessen erscheint ein zweisprachiger „Branding setzen“-Hinweis, und Tests erwarten nun leere Defaults.
- **EN:** Clarified the supported Python window (`>=3.11,<4.0`) to stop Streamlit deployments from pinning Python 4 previews that conflict with packages such as `backoff`.
  **DE:** Unterstützten Python-Zeitraum (`>=3.11,<4.0`) präzisiert, damit Streamlit-Deployments keine Python-4-Previews wählen, die mit Paketen wie `backoff` kollidieren.
- **EN:** Relaxed the OpenAI SDK requirement to permit the 2.x releases, matching the version available in Streamlit's build environment and unblocking deployments.
  **DE:** Die OpenAI-SDK-Anforderung gelockert, sodass jetzt auch 2.x-Releases erlaubt sind – entspricht der in der Streamlit-Build-Umgebung verfügbaren Version und behebt Deploy-Blocker.
- **EN:** Finalised the wizard navigation: the eight Streamlit pages now follow
  the file order `01_jobad.py` → `08_summary.py`, all legacy step-order flags
  have been removed, and navigation now always uses the step-order router after
  retiring the legacy runner.
  **DE:** Wizard-Navigation finalisiert: Die acht Streamlit-Seiten folgen der
  Dateireihenfolge `01_jobad.py` → `08_summary.py`, sämtliche veralteten
  Step-Order-Schalter wurden entfernt und der Step-Order-Router ersetzt den
  Legacy-Lauf vollständig.
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
  `constants/keys.ProfilePaths`, with the wizard schema available by default.
  **DE:** Die Schema-Schicht um `NeedAnalysisProfile` vereinheitlicht: Wizard-
  Bindings und Exporte verwenden dieselben kanonischen Dot-Pfade aus
  `constants/keys.ProfilePaths`; der Wizard greift standardmäßig auf diese
  Struktur zu.
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
- **EN:** Ensured the Poetry dependency set requires `openai>=1.30.0` so the Responses API tooling matches the pip requirements.
  **DE:** Poetry-Abhängigkeiten verlangen nun `openai>=1.30.0`, damit das Responses-API-Tooling mit den pip-Requirements übereinstimmt.
- **EN:** Hardened optional profile URL sanitisation so canonicalisation and wizard updates trim blanks to `None`, preventing schema resets.
  **DE:** Optionale Profil-URLs weiter gehärtet: Kanonisierung und Wizard-Updates kürzen leere Werte jetzt auf `None`, sodass keine Schema-Resets mehr ausgelöst werden.
- **EN:** Downgraded rule-matcher logs when phone or country values are absent so optional contact fields no longer emit warning-level noise.
  **DE:** Log-Ausgabe des Regelabgleichs herabgestuft, wenn Telefon- oder Länderdaten fehlen, sodass optionale Kontaktfelder keine Warnungen mehr erzeugen.
- **EN:** Rerouted lightweight tasks to `gpt-4.1-mini` and escalated reasoning-heavy flows to `o4-mini`, cascading through `o3` and `gpt-4o` automatically; environment overrides now normalise to these tiers.
  **DE:** Leichte Aufgaben laufen nun auf `gpt-4.1-mini`, während Zusammenfassungen und Erklärungen automatisch auf `o4-mini` (mit Fallbacks über `o3` und `gpt-4o`) eskalieren; Umgebungs-Overrides werden auf diese Stufen normalisiert.
- **EN:** Resolved duplicate Streamlit widget keys for branding uploads by giving the legacy wizard uploader its own identifier and clearing both caches together.
  **DE:** Doppelte Streamlit-Widget-Keys beim Branding-Upload behoben, indem der Legacy-Wizard einen eigenen Schlüssel erhält und beide Caches gemeinsam geleert werden.
- **EN:** Consolidated dependency management so `pyproject.toml` is the deployment source of truth and Streamlit no longer detects competing dependency manifests.
  **DE:** Abhängigkeitsverwaltung konsolidiert, sodass `pyproject.toml` als Deployment-Quelle dient und Streamlit keine konkurrierenden Abhängigkeitsdateien mehr meldet.
- **EN:** Slimmed the default requirement set to core app dependencies and exposed optional OCR/spaCy extras via the `ingest` extra (`pip install .[ingest]`) for contributors who need advanced ingestion features.
  **DE:** Die Standard-Requirements auf zentrale App-Abhängigkeiten verschlankt und optionale OCR-/spaCy-Erweiterungen über das Extra `ingest` (`pip install .[ingest]`) verfügbar gemacht, damit Contributor:innen bei Bedarf die erweiterten Ingestion-Funktionen aktivieren können.
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
- **EN:** The UI now boots directly on the RecruitingWizard schema: session state stores the Company/Department/Team payload, wizard pages highlight the canonical fields, and exports read `WIZARD_KEYS_CANONICAL` with alias-backed fallbacks.
  **DE:** Die Oberfläche startet jetzt direkt im RecruitingWizard-Schema: Der Session-State enthält Company-/Department-/Team-Daten, die Wizard-Seiten heben die kanonischen Felder hervor und Exporte nutzen `WIZARD_KEYS_CANONICAL` mit Alias-Fallbacks.
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
