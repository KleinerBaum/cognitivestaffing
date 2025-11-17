Changelog
v1.1.0 – Wizard Hardening & Schema Alignment / Wizard-Härtung & Schemaabgleich (2025-11-19)

EN: Introduced a config.set_api_mode() helper that flips both USE_RESPONSES_API and USE_CLASSIC_API atomically and wired it to a new bilingual debug panel in the wizard UI. Admins can now enable verbose error diagnostics and switch between the Responses and classic Chat APIs at runtime while downstream modules instantly read the updated config flags.
DE: Ein neuer Helfer config.set_api_mode() aktualisiert USE_RESPONSES_API und USE_CLASSIC_API jetzt atomar und ist mit einem zweisprachigen Debug-Panel im Wizard verknüpft. Admins können so ausführliche Fehlerdiagnosen aktivieren und zur Laufzeit zwischen Responses- und Chat-Completions-API wechseln, wobei nachgelagerte Module die neuen Flags sofort sehen.

EN: Added scripts/check_localization.py plus tests/test_localization_scan.py so UI modules fail CI whenever English strings bypass tr() or i18n.STR, and documented the workflow in README.md.
DE: scripts/check_localization.py sowie tests/test_localization_scan.py ergänzen jetzt einen CI-Blocker, falls englische Texte ohne tr() oder i18n.STR in die UI gelangen; der Workflow ist zusätzlich in README.md dokumentiert.
EN: Extracted the wizard field/section metadata into wizard/metadata.py and switched wizard_router plus its navigation tests to import it directly so the dependency chain stays explicit and type-checkable.
DE: Die Zuordnung zwischen Wizard-Feldern und Abschnitten in wizard/metadata.py verankert und wizard_router samt Navigationstests so angepasst, dass diese Metadaten direkt importiert werden – für explizite, typsichere Abhängigkeiten.

EN: The Follow-ups wizard step now blocks the “Next” button until every critical follow-up is answered, while normal questions remain optional, ensuring navigation only proceeds once mandatory clarifications are captured.
DE: Der Wizard-Schritt „Q&A“ sperrt den Button „Weiter“ so lange, bis alle kritischen Anschlussfragen beantwortet sind; normale Nachfragen bleiben optional, damit Pflichtangaben vor dem Fortfahren vollständig vorliegen.

EN: Refined the salary sidebar so estimates focus on the job title, core responsibilities, must-have and nice-to-have requirements, tools/tech/certificates, language expectations, industry, and city hints; the Streamlit navigation no longer exposes the redundant overview entry.
DE: Die Gehaltsschätzung nutzt jetzt Jobtitel, Kernaufgaben, Muss- und Nice-to-have-Anforderungen, Tools/Technologien/Zertifikate, Sprachvorgaben, Branche sowie Stadthinweise als Basis und blendet den überflüssigen Überblick-Link aus der Streamlit-Navigation aus.

EN: Added a bilingual “🔄 Reset wizard” control to the sidebar settings so talent teams can instantly clear the current profile while keeping their saved theme, language, and LLM-mode preferences intact.
DE: Einen zweisprachigen Button „🔄 Zurücksetzen / Reset wizard“ in die Sidebar-Einstellungen aufgenommen, mit dem Talent-Teams das Profil sofort zurücksetzen, während Dark-Mode-, Sprach- und LLM-Modus weiterhin erhalten bleiben.

EN: Replaced every use_container_width flag with the new width argument across Streamlit widgets to remove the 2025 deprecation warning while keeping the stretch layout intact.
DE: Sämtliche use_container_width-Schalter auf das neue width-Argument der Streamlit-Widgets umgestellt, damit die angekündigte Deprecation-Warnung für 2025 entfällt und das Stretch-Layout erhalten bleibt.

EN: The wizard progress tracker now counts each page’s required fields plus critical schema paths so Job Ad, Follow-ups, Interview, and Summary stay at 0 % until users complete them and never show 100 % when empty.
DE: Der Wizard-Fortschritt berücksichtigt jetzt die Pflichtfelder und kritischen Schema-Pfade aller Schritte, sodass Job-Ad, Follow-ups, Interview und Summary bei 0 % bleiben, bis sie abgeschlossen sind, und leer nicht länger 100 % anzeigen.

EN: Added a Quick vs Precise toggle in the settings sidebar that maps to gpt-4.1-mini/minimal reasoning or o4-mini/high reasoning, reuses cached structured extractions, and parallelises vector-store lookups for faster responses.
DE: Einen Schnell-/Präzisionsmodus in der Seitenleiste ergänzt, der zwischen gpt-4.1-mini mit minimalem Denkaufwand und o4-mini mit hohem Denkaufwand umschaltet, strukturierte Extraktionen cached und Vector-Store-Abfragen parallelisiert.

EN: Closed the Interview Guide Responses schema by enforcing additionalProperties: false on every object level and adding a regression test so OpenAI no longer rejects the format.
DE: Das Interview-Guide-Responses-Schema abgedichtet, indem additionalProperties: false auf allen Objekt-Ebenen erzwungen und ein Regressionstest ergänzt wurde, sodass OpenAI das Format wieder akzeptiert.

EN: Renamed all OpenAI helper parameters from max_tokens to max_completion_tokens so every Responses and Chat call uses the official field name and avoids unsupported-parameter warnings on the latest models.
DE: Sämtliche OpenAI-Helfer von max_tokens auf max_completion_tokens umgestellt, damit alle Responses- und Chat-Aufrufe den offiziellen Feldnamen nutzen und neue Modelle keine Warnungen wegen nicht unterstützter Parameter mehr ausgeben.

EN: Added a dedicated "Q&A" wizard step that surfaces generated follow-up questions right after extraction, complete with interactive input widgets to capture SME responses inline.
DE: Einen eigenen "Q&A"-Wizard-Schritt ergänzt, der die generierten Anschlussfragen direkt nach der Extraktion bündelt und mit interaktiven Eingabefeldern für unmittelbares Eintragen der SME-Antworten versieht.

EN: Hardened benefit suggestions by cascading through the legacy Chat backend before falling back to the static shortlist when Responses output is missing or malformed.
DE: Benefit-Vorschläge robuster gemacht, indem vor der statischen Shortlist zuerst der Legacy-Chat-Backend-Aufruf versucht wird, falls die Responses-Antwort fehlt oder fehlerhaft ist.

EN: Retired the last Wizard v1 scaffolding – removed the unused wizard_state['feature'] bootstrap and the deprecated core.schema aliases/coerce_and_fill_wizard helper now that the SCHEMA_WIZARD_V1 flag is gone for good, and added a regression test that fails if those legacy strings reappear in Python sources.
DE: Letzte Wizard-v1-Stützen entfernt – der ungenutzte wizard_state['feature']-Bootstrap sowie die veralteten core.schema-Aliasse bzw. der coerce_and_fill_wizard-Helper sind nach dem endgültigen Aus für SCHEMA_WIZARD_V1 gelöscht; zusätzlich prüft ein Regressionstest, dass diese Legacy-Strings nicht zurückkehren.

EN: Integrated LangChain’s StructuredOutputParser and PydanticOutputParser into the extraction stack so prompts ship with generated format instructions and responses deserialize straight into NeedAnalysisProfile without manual JSON plumbing.
DE: LangChains StructuredOutputParser und PydanticOutputParser im Extraktions-Stack verankert, sodass Prompts automatische Format-Hinweise erhalten und Antworten ohne manuelle JSON-Nachbearbeitung direkt in NeedAnalysisProfile einfließen.

EN: Polished the Streamlit experience with a branded hero banner, a three-tab summary layout (Profile overview, Insights, Export), an interactive Plotly salary visualisation, and an ESCO skill explorer that caches descriptions for fast lookups.
DE: Die Streamlit-Erfahrung mit gebrandetem Hero-Banner, dreigeteilter Zusammenfassung („Profilübersicht“, „Insights“, „Export“), interaktiver Plotly-Gehaltssicht und einem ESCO-Skill-Explorer mit gecachten Beschreibungen verfeinert.

EN: Added dedicated department.* and team.* profile sections, a customer-contact flag for position.*, and requirement toggles for background, reference, and portfolio checks. Step 3 (Team & Context) now binds these fields end-to-end, the follow-up logic validates them as critical before advancing, and the schema propagation script refreshes generated components.
DE: Eigene department.*- und team.*-Profilebenen ergänzt, einen Kundenkontakt-Schalter für position.* eingeführt und Anforderungs-Toggles für Background-, Referenz- und Portfolio-Prüfungen hinzugefügt. Schritt 3 („Team & Kontext“) bindet die Felder durchgängig ein, die Folgefragen-Logik behandelt sie vor dem Weiterklicken als kritisch und das Schema-Propagation-Skript aktualisiert die generierten Komponenten.

EN: Rebuilt the onboarding entry experience with a five-line bilingual briefing on OpenAI/ESCO-powered intake, centred URL/upload inputs of equal width, retired the manual text area, and swapped the green gradient CTA for a compact continue control.
DE: Das Onboarding neu inszeniert: Fünf zweisprachige Briefing-Zeilen zu OpenAI-/ESCO-gestützter Intake, mittig ausgerichtete URL-/Upload-Felder in gleicher Breite, das manuelle Textfeld entfernt und den grünen Gradient-CTA durch einen kompakten Weiter-Button ersetzt.

EN: The onboarding URL/upload fields and continue button stay disabled (with a bilingual hint) until an OpenAI API key unlocks LLM ingestion, so users cannot trigger uploads while AI features are offline.
DE: Onboarding-URL-/Upload-Felder sowie der Weiter-Button bleiben (mit zweisprachigem Hinweis) deaktiviert, bis ein OpenAI-API-Schlüssel die LLM-Intake freischaltet – dadurch lassen sich keine Uploads starten, wenn die KI-Funktionen offline sind.

EN: Updated the onboarding continue CTA to display the compact Weiter ▶ / Next ▶ label using the primary button styling from the compact CTA spec, ensuring the entry step mirrors the refreshed design tokens.
DE: Der Onboarding-Weiter-CTA zeigt nun das kompakte Label Weiter ▶ / Next ▶ mit dem Primary-Button-Styling der kompakten CTA-Spezifikationen, damit der Einstiegs-Schritt die erneuerten Design-Tokens widerspiegelt.

EN: Rolled out a tabbed extraction review in step 1 with editable company, role, logistics, requirements, and process tabs, added an interactive completion tracker across all eight steps, modernised follow-up questions with chip suggestions and field-aware widgets, and derived the brand colour from uploaded logos to auto-fill company.brand_color.
DE: Eine tabbasierte Extraktionsübersicht im ersten Schritt eingeführt, in der Unternehmens-, Rollen-, Logistik-, Anforderungs- und Prozessdaten sofort bearbeitbar sind; ein interaktiver Fortschrittstracker über alle acht Schritte zeigt den Erfüllungsgrad, Anschlussfragen nutzen Chip-Vorschläge und feldspezifische Widgets und hochgeladene Logos liefern automatisch die Markenfarbe für company.brand_color.

EN: Streamlined the sidebar by removing page navigation links, stacking the dark-mode and language switches vertically with flag icons, and triggering salary estimates automatically once job title plus a location hint are available; the panel now lists required fields, summarises the top five drivers in one sentence, and exposes the raw calculation data.
DE: Die Sidebar wurde verschlankt: Seiten-Links entfernt, Dark-Mode- und Sprachumschalter untereinander mit Flaggen-Icons angeordnet und Gehaltsschätzungen starten automatisch, sobald Jobtitel und ein Standorthinweis vorliegen; die Ansicht zeigt die benötigten Felder, fasst die fünf wichtigsten Faktoren in einem Satz zusammen und blendet die Berechnungsdaten sichtbar ein.

EN: Removed the legacy wizard.layout widget helpers; the widget factory now wires Streamlit inputs directly to _update_profile and exposes the bindings via wizard.wizard.
DE: Die veralteten wizard.layout-Widget-Helfer entfernt; die Widget-Factory verbindet Streamlit-Inputs jetzt direkt mit _update_profile und stellt die Bindings über wizard.wizard bereit.

EN: Introduced the RESPONSES_ALLOW_TOOLS feature flag: tool payloads stay disabled on Responses by default for the 2025 rollout, while the client automatically falls back to the chat backend whenever tools are required unless the flag is set to 1.
DE: Das Feature-Flag RESPONSES_ALLOW_TOOLS ergänzt: Tool-Payloads bleiben für den Responses-Rollout 2025 standardmäßig deaktiviert, und der Client wechselt automatisch auf das Chat-Backend, sobald Tools benötigt werden – außer das Flag steht auf 1.

EN: Switched the Requirements certificate synchronisation validator to the instance-based Pydantic v2 style, silencing deprecation warnings during tests and preparing the model for Pydantic 3.
DE: Den Validator zur Synchronisierung der Zertifikatslisten in Requirements auf die instanzbasierte Pydantic-v2-Schreibweise umgestellt, sodass die Deprecation-Warnung in den Tests entfällt und wir für Pydantic 3 vorbereitet sind.

EN: Normalised legacy helpers to snake_case and added missing return/argument type hints across wizard prompts, keeping linting strictness aligned with the repository-wide PEP 8 typing expectations.
DE: Legacy-Helfer auf snake_case umgestellt und fehlende Rückgabe- bzw. Argument-Typannotationen in Wizard-Prompts ergänzt, damit die strengen PEP-8-/Typing-Vorgaben des Repos konsistent bleiben.

EN: Expanded smoke and unit tests for the wizard agent tools (graph, knowledge, vacancy, safety) and page metadata to close coverage gaps and guard fallback behaviours.
DE: Smoke- und Unit-Tests für die Wizard-Agent-Tools (Graph, Knowledge, Vacancy, Safety) sowie die Seiten-Metadaten erweitert, um Abdeckungslücken zu schließen und Fallback-Verhalten abzusichern.

EN: Locked all OpenTelemetry packages to version 1.26.0, exposed the optional ingestion libraries via pyproject.toml, and refreshed artifacts/pip.freeze.txt so deployments use a consistent stack.
DE: Alle OpenTelemetry-Pakete auf Version 1.26.0 fixiert, die optionalen Ingestion-Bibliotheken in pyproject.toml abgebildet und artifacts/pip.freeze.txt aktualisiert, damit Deployments auf einem konsistenten Stack laufen.

EN: Excised the deprecated wizard._legacy runner and scrubbed remaining references so the Streamlit wizard always boots through WizardRouter.
DE: Den veralteten wizard._legacy-Runner vollständig entfernt und alle Restverweise bereinigt, sodass der Streamlit-Wizard konsequent über den WizardRouter startet.

EN: Removed the sidebar.* mypy ignore, introduced explicit type aliases, and tightened colour helpers so the sidebar module now passes static checks without suppressions.
DE: Das sidebar.*-Mypy-Ignorieren entfernt, explizite Type-Aliases ergänzt und die Farbhelfer präzisiert, sodass das Sidebar-Modul jetzt ohne Unterdrückungen die statischen Prüfungen besteht.

EN: Documented focused pytest loops in the developer guide, covering scoped modules, keyword filters, and marking known failures while expectations catch intentional behaviour changes.
DE: Fokussierte Pytest-Schleifen im Developer-Guide dokumentiert – mit Hinweisen zu Modul-Läufen, Stichwortfiltern sowie XFAIL-Markierungen und aktualisierten Erwartungen bei absichtlichen Verhaltensänderungen.

EN: Tuned the Mypy configuration to skip heavy third-party imports (streamlit, requests, bs4) while enforcing disallow_untyped_defs on wizard helpers so incremental cleanup can start without regressing strictness on new code.
DE: Die Mypy-Konfiguration angepasst: Umfangreiche Drittanbieter-Imports (streamlit, requests, bs4) werden per follow_imports = "skip" ausgelassen, während Wizard-Hilfen disallow_untyped_defs erzwingen, damit Aufräumarbeiten schrittweise starten können, ohne neue Lockerungen zu riskieren.

EN: Documented the baseline Mypy failures, added temporary ignore overrides for legacy modules, and published the checklist in docs/mypy_typing_status.md to guide future cleanups.
DE: Bestehende Mypy-Fehler dokumentiert, temporäre Ignore-Overrides für Legacy-Module ergänzt und die Checkliste in docs/mypy_typing_status.md festgehalten, um kommende Aufräumarbeiten zu steuern.

EN: Removed placeholder claim/logo defaults from the sidebar and replaced them with a bilingual “Set branding” call-to-action plus empty defaults in tests.
DE: Platzhalter für Claim und Logo in der Sidebar entfernt – stattdessen erscheint ein zweisprachiger „Branding setzen“-Hinweis, und Tests erwarten nun leere Defaults.

EN: Clarified the supported Python window (>=3.11,<4.0) to stop Streamlit deployments from pinning Python 4 previews that conflict with packages such as backoff.
DE: Unterstützten Python-Zeitraum (>=3.11,<4.0) präzisiert, damit Streamlit-Deployments keine Python-4-Previews wählen, die mit Paketen wie backoff kollidieren.

EN: Relaxed the OpenAI SDK requirement to permit the 2.x releases, matching the version available in Streamlit’s build environment and unblocking deployments.
DE: Die OpenAI-SDK-Anforderung gelockert, sodass jetzt auch 2.x-Releases erlaubt sind – entspricht der in der Streamlit-Build-Umgebung verfügbaren Version und behebt Deploy-Blocker.

EN: Finalised the wizard navigation: the eight Streamlit pages now follow the file order 01_jobad.py → 08_summary.py, all legacy step-order flags have been removed, and navigation now always uses the step-order router after retiring the legacy runner.
DE: Wizard-Navigation finalisiert: Die acht Streamlit-Seiten folgen der Dateireihenfolge 01_jobad.py → 08_summary.py, sämtliche veralteten Step-Order-Schalter wurden entfernt und der Step-Order-Router ersetzt den Legacy-Lauf vollständig.

EN: Chip multiselects now expose context-aware bilingual hints, guiding users when adding skills, benefits, languages, or job-ad sections.
DE: Chip-Multiselects zeigen nun kontextsensible zweisprachige Hinweise und führen beim Hinzufügen von Skills, Benefits, Sprachen oder Anzeigeninhalten.

EN: Updated the wizard to drop ACME/example.com placeholders, using bilingual helper text and empty schema defaults that mark required fields instead of demo values.
DE: Den Wizard von ACME-/example.com-Platzhaltern befreit: Jetzt geben zweisprachige Hinweise Orientierung, während leere Schema-Defaults Pflichtfelder kennzeichnen statt Demo-Werte zu befüllen.

EN: Unified the schema layer around NeedAnalysisProfile: wizard bindings and exports now consume the same canonical dot-paths from constants/keys.ProfilePaths, with the wizard schema available by default.
DE: Die Schema-Schicht um NeedAnalysisProfile vereinheitlicht: Wizard-Bindings und Exporte verwenden dieselben kanonischen Dot-Pfade aus constants/keys.ProfilePaths; der Wizard greift standardmäßig auf diese Struktur zu.

EN: Prevent ESCO placeholder URIs from contacting the live API by serving cached essential skills whenever offline fixtures include the identifier.
DE: Verhindert, dass ESCO-Platzhalter-URIs die Live-API erreichen, indem gespeicherte Kernkompetenzen genutzt werden, sobald Offline-Fixdaten die Kennung enthalten.

EN: Refreshed README, developer guide, key registry, and JSON pipeline docs to describe the unified schema, current field names, and the latest wizard flow in English and German.
DE: README, Developer-Guide, Key-Registry und JSON-Pipeline-Doku überarbeitet – mit einheitlichem Schema, aktuellen Feldnamen und dem neuesten Wizard-Fluss auf Deutsch und Englisch.

EN: Documented the repository folder structure so maintainers can map modules like pages/, wizard/, and core/ at a glance.
DE: Die Projektordner dokumentiert, damit Maintainer:innen Verzeichnisse wie pages/, wizard/ und core/ auf einen Blick zuordnen können.

EN: Refined the Summary step with a dedicated "Create a job ad" section featuring a compact field selector, collapsible preferences, and kept manual additions next to the generation controls while relocating the internal-process review to the Process step.
DE: Den Summary-Schritt überarbeitet: Eigener Bereich „Stellenanzeige erstellen“ mit kompakter Feldauswahl und einklappbaren Präferenzen, manuelle Ergänzungen beim Generator belassen und die Übersicht „Interne Prozesse definieren“ in den Prozess-Schritt verschoben.

EN: Routed company web enrichment through _update_profile so “Get Info from Web” immediately mirrors updates across sidebar and form inputs.
DE: Unternehmens-Webanreicherungen laufen nun über _update_profile, damit „Infos aus dem Web holen“ Änderungen sofort in Sidebar und Formular widerspiegelt.

EN: Replaced unsupported format: "uri" markers in the Need Analysis schema with URL patterns, added a whitelist-based sanitizer before Responses API calls, and kept the persisted schema in lockstep.
DE: Nicht unterstützte format: "uri"-Marker im Need-Analysis-Schema durch URL-Pattern ersetzt, einen Whitelist-Sanitizer vor Responses-Aufrufen ergänzt und das persistierte Schema synchronisiert.

EN: Introduced the Aurora Fjord palette across both themes and the skill board, blending midnight blues with glacial aqua and ember accents to steady hierarchy and boost contrast.
DE: Die Aurora-Fjord-Palette in beiden Themes und dem Skill-Board eingebracht – Mitternachtsblau, Gletscher-Aqua und Amber-Akzente stabilisieren die Hierarchie und verbessern den Kontrast.

EN: Enforced an 88% coverage floor in CI, uploaded coverage HTML/XML artifacts, and defaulted llm-tagged tests to opt-in mode so heuristics stay guarded without blocking offline contributors.
DE: In der CI gilt jetzt eine Abdeckungsuntergrenze von 88 %, Coverage-HTML/XML-Artefakte werden hochgeladen und llm-markierte Tests bleiben optional, sodass Heuristiken geschützt werden, ohne Offline-Contributor:innen auszubremsen.

EN: Prevented Streamlit duplicate-key crashes for branding uploads by namespacing the sidebar uploader and persisting assets via safe callbacks.
DE: Streamlit-Abstürze durch doppelte Branding-Upload-Keys verhindert, indem der Sidebar-Uploader einen eigenen Namespace erhält und Assets über sichere Callbacks gespeichert werden.

EN: Migrated legacy session keys such as company_name and contact_email to the canonical wizard schema paths so scraped profiles prefill the company/contact forms, and aligned the widget factories with the default get_value/_update_profile callbacks.
DE: Legacy-Session-Keys wie company_name und contact_email werden nun auf die kanonischen Wizard-Schema-Pfade gemappt, sodass Scrapes die Unternehmens- und Kontakt-Formulare vorbefüllen; die Widget-Factories nutzen dabei standardmäßig das get_value/_update_profile-Callback-Muster.

EN: Improved Rheinbahn ingestion heuristics: detect “suchen wir in …” cities, route benefit keywords to company.benefits, and parse footer contacts with confidence metadata.
DE: Rheinbahn-Heuristiken verbessert: Städte aus “suchen wir in …” erkennen, Benefit-Schlagworte nach company.benefits mappen und Footer-Kontakte inklusive Vertrauensmetadaten parsen.

EN: Ensured the Poetry dependency set requires openai>=1.30.0 so the Responses API tooling matches the pip requirements.
DE: Poetry-Abhängigkeiten verlangen nun openai>=1.30.0, damit das Responses-API-Tooling mit den pip-Requirements übereinstimmt.

EN: Hardened optional profile URL sanitisation so canonicalisation and wizard updates trim blanks to None, preventing schema resets.
DE: Optionale Profil-URLs weiter gehärtet: Kanonisierung und Wizard-Updates kürzen leere Werte jetzt auf None, sodass keine Schema-Resets mehr ausgelöst werden.

EN: Downgraded rule-matcher logs when phone or country values are absent so optional contact fields no longer emit warning-level noise.
DE: Log-Ausgabe des Regelabgleichs herabgestuft, wenn Telefon- oder Länderdaten fehlen, sodass optionale Kontaktfelder keine Warnungen mehr erzeugen.

EN: Rerouted lightweight tasks to gpt-4.1-mini and escalated reasoning-heavy flows to o4-mini, cascading through o3 and gpt-4o automatically; environment overrides now normalise to these tiers.
DE: Leichte Aufgaben laufen nun auf gpt-4.1-mini, während Zusammenfassungen und Erklärungen automatisch auf o4-mini (mit Fallbacks über o3 und gpt-4o) eskalieren; Umgebungs-Overrides werden auf diese Stufen normalisiert.

EN: Resolved duplicate Streamlit widget keys for branding uploads by giving the legacy wizard uploader its own identifier and clearing both caches together.
DE: Doppelte Streamlit-Widget-Keys beim Branding-Upload behoben, indem der Legacy-Wizard einen eigenen Schlüssel erhält und beide Caches gemeinsam geleert werden.

EN: Consolidated dependency management so pyproject.toml is the deployment source of truth, removed the legacy requirements.txt, and updated deployment scripts to run pip install ./pip install .[dev].
DE: Abhängigkeitsverwaltung konsolidiert: pyproject.toml dient als Deployment-Quelle, das alte requirements.txt wurde entfernt und Deploy-Skripte nutzen jetzt pip install . bzw. pip install .[dev].

EN: Slimmed the default requirement set to core app dependencies and exposed optional OCR/spaCy extras via the ingest extra (pip install .[ingest]) for contributors who need advanced ingestion features.
DE: Die Standard-Requirements auf zentrale App-Abhängigkeiten verschlankt und optionale OCR-/spaCy-Erweiterungen über das Extra ingest (pip install .[ingest]) verfügbar gemacht, damit Contributor:innen bei Bedarf die erweiterten Ingestion-Funktionen aktivieren können.

EN: CI, Dev Containers, and Streamlit Cloud now bootstrap dependencies through pip install ./pip install .[dev], keeping pyproject.toml as the single manifest and guaranteeing extras stay installable from the same metadata.
DE: CI, Dev-Container und Streamlit-Cloud-Deployments laden Abhängigkeiten jetzt über pip install . bzw. pip install .[dev], sodass pyproject.toml alleinige Quelle bleibt und Extras über dieselben Metadaten zuverlässig installierbar sind.

EN: Added PyMuPDF to the primary dependency list so PDF exports for interview guides run on fresh environments without manual installs.
DE: PyMuPDF zur primären Abhängigkeitsliste hinzugefügt, damit PDF-Exporte der Interview-Guides in neuen Umgebungen ohne manuelle Installation funktionieren.

EN: Removed the unused configloader and tenacity dependencies from requirements.txt to keep deployments leaner.
DE: Die ungenutzten Abhängigkeiten configloader und tenacity aus requirements.txt entfernt, um Deployments schlanker zu halten.

EN: Updated the skill market fallback caption to explain that benchmarks are missing and encourage capturing skill data instead of showing neutral placeholder numbers.
DE: Die Skill-Markt-Fallback-Beschriftung angepasst: Sie erklärt nun das Fehlen von Benchmarks und fordert zum Erfassen von Skill-Daten auf, statt neutrale Platzhalterzahlen darzustellen.

EN: Moved the sidebar “Benefit ideas” module into the Rewards & Benefits step and positioned the step summary directly above each wizard header.
DE: Das Sidebar-Modul „Benefit-Ideen“ in den Schritt „Leistungen & Benefits“ verschoben und die Schrittübersicht direkt über jede Wizard-Überschrift gesetzt.

EN: Simplified the Summary step layout by dropping the Key highlights block and moving the JSON export button to the bottom for clearer final actions.
DE: Das Layout des Zusammenfassungs-Schritts vereinfacht: Der Block „Wesentliche Eckdaten“ entfällt und der JSON-Export-Button steht jetzt unten für klarere Abschlussaktionen.

EN: Added regression tests for phone number and website URL normalisation to guard the wizard’s new validation paths.
DE: Regressions-Tests für die Normalisierung von Telefonnummern und Website-URLs ergänzt, um die neuen Validierungspfade des Wizards zu schützen.

v1.0.1 – Setup & Branding Refresh / Setup- & Branding-Update (2025-11-05)
Added / Neu

EN: Branding parser now enriches profiles with company.logo_url, company.brand_color, and company.claim, wiring the logo and claim into the sidebar hero and exports.
DE: Der Branding-Parser ergänzt Profile um company.logo_url, company.brand_color und company.claim, sodass Logo und Claim in Sidebar und Exporten erscheinen.

EN: Documented OpenAI configuration pathways (environment variables, Streamlit secrets, EU base URL) including in-app warnings when the key is missing.
DE: OpenAI-Konfigurationswege (Umgebungsvariablen, Streamlit-Secrets, EU-Basis-URL) dokumentiert – inklusive In-App-Warnung, falls der Schlüssel fehlt.

EN: Added contributor guidance for the normalization pipeline, feature flags, and ProfilePaths widget bindings in README and developer docs.
DE: Entwicklerleitfaden für Normalisierungspipeline, Feature-Flags und ProfilePaths-Widget-Bindungen in README und Doku ergänzt.

Fixed / Behoben

EN: Resolved the Company step autofill crash caused by branding assets missing dominant colours.
DE: Absturz der Unternehmens-Autofill-Logik behoben, wenn Branding-Assets keine dominanten Farben lieferten.

EN: Hardened structured extraction payload handling to recover gracefully from invalid JSON envelopes.
DE: Verarbeitung der strukturierten Extraktions-Payload gehärtet, sodass ungültige JSON-Hüllen sauber abgefangen werden.

EN: Fixed media uploads that previously failed when file names contained non-ASCII characters.
DE: Fehler bei Medien-Uploads korrigiert, wenn Dateinamen Nicht-ASCII-Zeichen enthielten.

Refactored / Refaktoriert

EN: Unified schema keys via constants.keys.ProfilePaths across wizard steps, state synchronisation, and exports (CS_SCHEMA_PROPAGATE).
DE: Schema-Keys über constants.keys.ProfilePaths zwischen Wizard, State-Sync und Exporten vereinheitlicht (CS_SCHEMA_PROPAGATE).

Docs / Doku

EN: README now highlights feature flags, Poppler/Tesseract prerequisites, and the extraction → normalisation pipeline.
DE: README weist nun auf Feature-Flags, Poppler/Tesseract-Voraussetzungen und die Extraktions-→-Normalisierungspipeline hin.

EN: Added developer snippets for creating wizard fields and extending rule-based extraction.
DE: Entwickler-Snippets für neue Wizard-Felder und die Erweiterung regelbasierter Extraktion ergänzt.

v1.0.0 – Wizard-Vollmodernisierung & KI-Assistenten (2025-10-27)

feat: standardise wizard layout, schema keys, and export mapping across all steps (CS_SCHEMA_PROPAGATE)

Feature: Wizard-Layout, Schema-Keys und Export-Mapping für alle Schritte vereinheitlicht (CS_SCHEMA_PROPAGATE)

feat: add pragmatic/formal/casual intro captions (EN/DE) to every step via panel_intro_variants

Feature: Pragmatische, formelle und lockere Intro-Captions (DE/EN) für jeden Schritt über panel_intro_variants

feat: expand AI helpers with refreshed skill/benefit/responsibility suggestions and interview guide generation

Feature: KI-Helfer für Skills, Benefits, Verantwortlichkeiten und Interview-Guides erweitert

refactor: extract reusable wizard components for suggestion chips, inputs, and state sync

Refactor: Wiederverwendbare Wizard-Komponenten für Suggestion-Chips, Eingaben und State-Sync extrahiert

feat: streamline navigation UX with top-of-step focus, responsive layout, and mobile stacking

Feature: Navigations-UX mit Top-of-Step-Fokus, responsivem Layout und Mobile-Stacking optimiert

fix: correct invalid city fallbacks and reassign flexible hours to employment work schedule (CS_SCHEMA_PROPAGATE)

Fix: Ungültige Städtewerte korrigiert und flexible Arbeitszeiten dem Arbeitszeitplan zugeordnet (CS_SCHEMA_PROPAGATE)

fix: gate AI suggestions behind explicit user triggers and reset caches on refresh

Fix: KI-Vorschläge nur nach aktiver Auslösung und Cache-Reset bei Aktualisierung

fix: cover outstanding wizard regression tests for skill board, legacy state, and error banners

Fix: Ausstehende Wizard-Regressionstests für Skill-Board, Legacy-State und Fehlermeldungen abgedeckt

docs: capture unified design tokens, hover/focus styling, and mobile accessibility guidance

Dokumentation: Einheitliche Design-Tokens, Hover/Fokus-Styling und mobile Accessibility-Anleitung dokumentiert

chore: align linting, mypy checks, and deployment requirements for the release train

Chore: Linting-, mypy-Prüfungen und Deployment-Requirements für den Release-Train abgestimmt

docs: update README and changelog, bump version identifiers to 1.0.0, and confirm release readiness

Dokumentation: README und Changelog aktualisiert, Versionsnummern auf 1.0.0 gesetzt und Release-Bereitschaft bestätigt
