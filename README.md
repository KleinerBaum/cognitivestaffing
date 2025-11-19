Cognitive Staffing

Cognitive Staffing automates the extraction and enrichment of vacancy profiles from PDFs, URLs, or pasted text. It turns unstructured job ads into structured JSON, highlights missing data, and orchestrates multiple AI agents to draft follow-up questions, job ads, interview guides, and Boolean searches. By default, all LLM calls run through the OpenAI Responses API using cost-effective models: lightweight tasks run on gpt-4.1-mini, while reasoning-heavy flows (summaries, explanations, document rewrites) escalate to the Responses reasoning tier o4-mini with automatic fallbacks through o3 and gpt-4o. This setup lets us enforce structured outputs, stream long generations, and fall back gracefully when rate limits occur. If needed, set the USE_CLASSIC_API environment variable to route all calls through the standard Chat Completions API instead.

Key highlights / Wichtigste Funktionen

EN:
* Eight-step wizard flow (Onboarding → Summary) with inline follow-up cards keeps SMEs inside a single context, combines extraction review plus guided data entry, and wires every field back to NeedAnalysisProfile.
* Automatic salary estimation launches as soon as job title and location hints exist, displaying required fields, drivers, and raw benchmark calculations in the sidebar.
* The wizard canvas now keeps the header distraction-free – the debug/API controls and per-step progress bubbles stay hidden so each step focuses purely on form inputs and inline follow-ups (API mode changes remain governed by config flags in the background).
* Inline error boundaries keep the wizard session alive even when parsing or Streamlit widgets fail, surfacing bilingual guidance so SMEs can continue with manual edits instead of losing their progress.

DE:
* Achtstufiger Wizard (Onboarding → Summary) mit Inline-Follow-up-Karten hält Fachexpert:innen im Kontext, kombiniert Extraktionsreview und geführte Eingabe und schreibt jede Angabe ins NeedAnalysisProfile zurück.
* Automatische Gehaltsschätzungen starten, sobald Jobtitel und Standort-Hinweis vorhanden sind, und zeigen Pflichtfelder, Einflussfaktoren sowie die Rohberechnung in der Seitenleiste an.
* Der Wizard-Canvas bleibt jetzt komplett aufgeräumt – Debug-/API-Steuerung und Fortschrittsblasen sind ausgeblendet, damit sich jede Stufe ausschließlich auf die Eingabefelder und Inline-Follow-ups konzentriert (API-Modus-Umschaltungen laufen weiterhin über die Konfiguration im Hintergrund).
* Fehlergrenzen direkt im Wizard sorgen dafür, dass Sitzungen bei Parser- oder Streamlit-Ausnahmen nicht abbrechen, sondern mit zweisprachiger Anleitung zum manuellen Weiterarbeiten geöffnet bleiben.

Version

EN: Current release: v1.1.0 (November 2025) – see below for highlights.

DE: Aktuelle Version: v1.1.0 (November 2025) – Highlights siehe unten.

Release timeline / Release-Verlauf

* Unreleased – Extraction resilience: structured JSON parsing now repairs interview stage lists, records validation errors, and surfaces bilingual warnings when a profile falls back to defaults so recruiters know which fields to fix.
* Unveröffentlicht – Extraktionsrobustheit: Der strukturierte JSON-Parser korrigiert jetzt Interview-Phasenlisten, protokolliert Validierungsfehler und blendet zweisprachige Warnungen ein, sobald ein Profil auf Standardwerte zurückgesetzt wird – so wissen Recruiter:innen sofort, welche Felder nachgepflegt werden müssen.
* EN: The Company step revalidates the contact email and primary city during navigation, showing a bilingual warning under the Next controls and preventing progress until both fields contain real data.
* DE: Der Unternehmensschritt prüft Kontakt-E-Mail und Primärstadt jetzt zusätzlich bei der Navigation, blendet direkt unter „Weiter“ einen zweisprachigen Hinweis ein und lässt erst weiterklicken, wenn beide Felder echte Werte enthalten.
* v1.1.0 – Wizard hardening & schema alignment: inline follow-ups inside all eight steps, automatic salary estimation refresh, quick/precise routing toggle, debug panel, and Responses ↔ Chat switching helper.
* v1.0.1 – Setup & branding refresh: company branding enrichment, OpenAI configuration guidance, contributor docs for schema propagation, and extraction hardening.
* v1.0.0 – Wizard modernisation: unified layout, schema/export propagation, AI helpers for responsibilities/interviews, navigation refresh, and release of the eight-step intake.

* v1.1.0 – Wizard-Härtung & Schemaabgleich: Inline-Follow-ups in allen acht Schritten, automatische Gehaltsupdates, Schnell-/Präzisionsmodus, Debug-Panel und Umschalter zwischen Responses- und Chat-API.
* v1.0.1 – Setup- & Branding-Update: Branding-Anreicherung fürs Unternehmen, OpenAI-Konfigurationshinweise, Contributor-Doku zur Schema-Propagation und stabilere Extraktion.
* v1.0.0 – Wizard-Vollmodernisierung: Vereinheitlichtes Layout, Schema-/Export-Sync, KI-Helfer für Verantwortlichkeiten/Interviews, Navigations-Refresh und Veröffentlichung des achtstufigen Intake-Prozesses.

Repository layout / Projektstruktur

EN: The repository keeps wizard-facing code under components/, pages/, wizard/, sidebar/, and ui_views/, while domain logic lives in core/, constants/, and schemas.py. LLM adapters stay inside llm/ and openai_utils/, ingestion/RAG helpers in ingest/ plus pipelines/, and documentation in docs/ with CHANGELOG, developer guides, and telemetry notes.

DE: Wizard-sichtbarer Code liegt in components/, pages/, wizard/, sidebar/ und ui_views/, während die Domänenlogik in core/, constants/ und schemas.py lebt. LLM-Adapter befinden sich in llm/ und openai_utils/, Ingestion-/RAG-Helfer in ingest/ sowie pipelines/, und die Dokumentation mit CHANGELOG, Developer-Guides und Telemetrie-Hinweisen unter docs/.

Testing / Tests

EN: Run ruff format, ruff check, and mypy --config-file pyproject.toml before executing coverage run -m pytest -q (the default marker expression skips llm tests; add -m llm when an OpenAI key is configured). Keep total coverage ≥88% so CI stays green and XML/HTML artifacts remain available for review.

DE: Führe ruff format, ruff check und mypy --config-file pyproject.toml aus und starte anschließend coverage run -m pytest -q (standardmäßig werden llm-Tests übersprungen; mit konfiguriertem OpenAI-Key kannst du -m llm ergänzen). Halte die Gesamtabdeckung bei ≥88 %, damit die CI grün bleibt und XML-/HTML-Artefakte für das Review bereitstehen.

Dependency management / Abhängigkeitsverwaltung

EN: Poetry 1.8+ now manages dependency installs without packaging the repository. Run `poetry install --no-root` (or append `--with ingest` when vectorisation helpers are required) to mirror the Streamlit Cloud deployment, which executes the same command via `infra/deployment.toml`. Because `[tool.poetry]` sets `package-mode = false`, Poetry simply reads `[project]` dependencies and extras – no `src/` layout or package build step is needed for local or cloud setups.

DE: Poetry 1.8+ übernimmt die Abhängigkeitsinstallation, ohne das Repository zu paketieren. Führe `poetry install --no-root` aus (optional mit `--with ingest`, falls die Vectorisierungs-Extras benötigt werden), damit deine lokale Umgebung exakt dem Streamlit-Cloud-Deployment entspricht – dort läuft derselbe Befehl gemäß `infra/deployment.toml`. Durch `package-mode = false` im Abschnitt `[tool.poetry]` nutzt Poetry direkt die Angaben unter `[project]`, sodass weder ein `src/`-Layout noch ein separater Build-Schritt für lokale oder Cloud-Setups erforderlich ist.

EN: Before opening a PR that touches sidebar/, pages/, components/, wizard/, or ui_views/, run python scripts/check_localization.py to ensure English UI strings stay wrapped in tr() or live inside i18n.STR. pytest tests/test_localization_scan.py enforces the same scan during CI to keep regressions out of dev.

DE: Bevor du einen PR mit Änderungen an sidebar/, pages/, components/, wizard/ oder ui_views/ erstellst, führe python scripts/check_localization.py aus, damit englische UI-Texte weiterhin in tr() gekapselt oder in i18n.STR hinterlegt sind. pytest tests/test_localization_scan.py erzwingt denselben Scan in der CI, damit keine Regressionen den dev-Branch erreichen.

EN: Track pre-existing typing gaps and the temporary ignore list in docs/mypy_typing_status.md so future branches can retire overrides incrementally.

DE: Dokumentierte Typing-Lücken sowie die temporären Ignore-Listen findest du in docs/mypy_typing_status.md, damit zukünftige Branches die Overrides schrittweise abbauen können.

EN: Heavy optional dependencies such as streamlit, requests, and bs4 are configured with follow_imports = "skip" so the type checker can focus on first-party fixes; replace skips with typed facades when the upstream packages ship stubs.

DE: Schwere optionale Abhängigkeiten wie streamlit, requests und bs4 laufen mit follow_imports = "skip", damit sich der Type-Checker auf First-Party-Bereiche konzentrieren kann; ersetze die Skips durch typisierte Fassaden, sobald die Upstream-Pakete Stubs liefern.

EN: Wizard helper modules (wizard._agents, _logic, _openai_bridge, interview_step, wizard) now require typed function signatures via disallow_untyped_defs; keep annotations complete when editing these files.

DE: Die Wizard-Hilfsmodule (wizard._agents, _logic, _openai_bridge, interview_step, wizard) erzwingen disallow_untyped_defs; achte bei Änderungen auf vollständige Typannotationen.

EN: Smoke tests cover every wizard page metadata file plus the wizard_tools agent shims. Run pytest tests/test_wizard_pages_smoke.py tests/test_wizard_tools_*.py when touching navigation metadata or tool fallbacks.

DE: Smoke-Tests decken alle Wizard-Seiten-Metadaten sowie die wizard_tools-Agenten ab. Führe pytest tests/test_wizard_pages_smoke.py tests/test_wizard_tools_*.py aus, sobald Navigations-Metadaten oder Tool-Fallbacks geändert werden.

What's new in v1.1.0 / Neu in v1.1.0

EN: The built-in Streamlit multi-page navigation (app/jobad/company/…) is now hidden entirely via the global theme, so only the curated wizard sidebar and its contextual helpers remain visible on the left.
DE: Die integrierte Streamlit-Multipage-Navigation (app/jobad/company/…) ist nun vollständig über das globale Theme ausgeblendet, sodass ausschließlich die kuratierte Wizard-Sidebar mit ihren Kontext-Helfern links sichtbar bleibt.

EN: Salary estimates now key off the job title, core responsibilities, must-have and nice-to-have requirements, tools/tech/certificates, language expectations, industry, and the provided city hint, and the default Streamlit navigation no longer shows the redundant overview entry. The Process step also exposes a numeric “Interview stages (count)” input so structured profiles keep `process.interview_stages` aligned with its integer schema.
DE: Gehaltsschätzungen orientieren sich jetzt an Jobtitel, Kernaufgaben, Muss- und Nice-to-have-Anforderungen, Tools/Technologien/Zertifikaten, Sprachvorgaben, Branche sowie der angegebenen Stadt; die Standard-Navigation von Streamlit blendet den überflüssigen Überblick-Eintrag aus. Im Prozess-Schritt sorgt ein numerisches Feld „Interviewstufen (Anzahl)“ dafür, dass `process.interview_stages` dem Integer-Schema entspricht.
EN: The Company step now blocks navigation until `company.contact_email` and `location.primary_city` are captured, showing bilingual helper copy and inline validation so exports always include a reachable contact and benchmark-ready location context.
DE: Der Unternehmensschritt lässt die Navigation erst weiterlaufen, wenn `company.contact_email` und `location.primary_city` ausgefüllt sind – inklusive zweisprachiger Hilfetexte und Inline-Validierung, damit Exporte stets einen erreichbaren Kontakt und den Standortanker für Benchmarks enthalten.

EN: Tightened the Company step gating so clearing `company.contact_email` or `location.primary_city` immediately disables “Next” again, surfacing the inline warning from `persist_contact_email()`/`persist_primary_city()` before recruiters can advance.
DE: Die Navigation im Unternehmensschritt verriegelt sich nun sofort wieder, sobald `company.contact_email` oder `location.primary_city` geleert werden – die Inline-Warnungen aus `persist_contact_email()` bzw. `persist_primary_city()` erscheinen direkt, bevor Recruiter:innen weiterklicken können.

EN: Streamlined the sidebar: navigation links are gone, language and dark-mode switches sit beneath each other with flag icons, and salary estimates now launch automatically once job title plus a location hint are present, listing required fields, summarising the top five drivers in a single sentence, and surfacing the raw calculation details.
DE: Sidebar verschlankt: Navigations-Links entfernt, Sprach- und Dark-Mode-Umschalter stehen untereinander mit Flaggen-Icons, und Gehaltsschätzungen starten automatisch, sobald Jobtitel und ein Standorthinweis vorliegen – inklusive Pflichtfeldliste, Ein-Satz-Zusammenfassung der fünf wichtigsten Faktoren und sichtbarer Berechnungsdetails.

EN: The eight-step workflow tracker moved into the sidebar between the quick snapshot and step context sections. Each step renders as a compact expander that highlights the current position and lists every schema key that already contains data so recruiters can audit captured inputs without scrolling back to the canvas.
DE: Der achtstufige Workflow-Tracker sitzt jetzt in der Sidebar zwischen Schnellüberblick und Schritt-Kontext. Jeder Schritt erscheint als kompakter Aufklapper, markiert die aktuelle Position und listet alle bereits befüllten Schemafelder auf, sodass Recruiter:innen die Eingaben prüfen können, ohne zum Hauptbereich zurückzuspringen.

EN: Normalise wizard widget defaults via _ensure_widget_state() so text inputs and list editors seed before rendering, avoiding Streamlit “Cannot set widget” errors on reruns.
DE: Normalisiert die Widget-Defaults im Wizard über _ensure_widget_state(), damit Textfelder und Listen-Editoren vor dem Rendern initialisiert werden und beim erneuten Ausführen keine “Cannot set widget”-Fehler mehr auftreten.

EN: Clean up company contact phones and websites across the wizard so noisy entries are normalised and cleared fields store None in the profile.
DE: Bereinigt Unternehmens-Telefonnummern und Websites im Wizard, normalisiert unruhige Eingaben und speichert geleerte Felder als None im Profil.

EN: Disable all AI suggestion buttons and generation actions when no OpenAI API key is configured, displaying a bilingual lock hint instead of triggering backend calls.
DE: Deaktiviert sämtliche KI-Vorschlagsbuttons und Generierungsaktionen, sobald kein OpenAI-API-Schlüssel hinterlegt ist, und zeigt stattdessen einen zweisprachigen Hinweis an.

EN: Unified Responses API retry handling now logs warnings and automatically falls back to chat completions or static content when structured calls fail or return invalid JSON.
DE: Vereinheitlichte Responses-Retry-Logik protokolliert Warnungen und schaltet automatisch auf Chat-Completions oder statische Inhalte um, wenn strukturierte Aufrufe scheitern oder ungültiges JSON liefern.

EN: Enforced full NeedAnalysisProfile ↔ wizard alignment: every schema field now has a canonical ProfilePaths entry, appears in the wizard panels, and propagates into exports with regression tests guarding drift.
DE: Vollständige NeedAnalysisProfile↔Wizard-Ausrichtung umgesetzt: Jedes Schemafeld besitzt nun einen kanonischen ProfilePaths-Eintrag, wird in den Wizard-Panels angezeigt und in Exporte übernommen, abgesichert durch Regressionstests gegen Abweichungen.

EN: Refined the salary sidebar: the panel now highlights the latest estimate with its source, charts top factors via Plotly, and falls back to curated benefit shortlists whenever the AI returns no suggestions.
DE: Salary-Sidebar überarbeitet: Die Ansicht zeigt nun die aktuelle Schätzung samt Quelle, visualisiert die wichtigsten Einflussfaktoren mit Plotly und blendet bei ausbleibenden KI-Vorschlägen automatisch die kuratierte Benefit-Shortlist ein.

EN: Sidebar branding overrides let you upload a logo, pick a brand colour, and edit the claim; exports and job ads now embed that metadata by default.
DE: Branding-Overrides in der Sidebar ermöglichen Logo-Uploads, die Auswahl der Markenfarbe und das Bearbeiten des Claims; Exporte und Stellenanzeigen übernehmen diese Metadaten automatisch.

EN: Inline follow-up cards now sit directly beneath the affected section and keep the “Next” button disabled until every critical question has a response, while informational prompts remain optional. This keeps mandatory clarifications in context without forcing a separate page.
DE: Inline-Follow-up-Karten erscheinen direkt unter dem jeweiligen Abschnitt und sperren „Weiter“, bis alle kritischen Fragen beantwortet sind; optionale Nachfragen bleiben freiwillig. So lassen sich Pflichtangaben im Kontext klären, ohne einen eigenen Q&A-Schritt zu öffnen.
EN: Metadata for the Role, Skills, Benefits, and Process steps now references the canonical NeedAnalysisProfile field names, so required-field gating, collected-value chips, and exports stay aligned while inline follow-ups simply prefill the visible widgets instead of racing `_update_profile`.
DE: Die Metadaten der Schritte Rolle, Skills, Benefits und Prozess greifen jetzt auf die kanonischen NeedAnalysisProfile-Feldnamen zu, sodass Pflichtfeldprüfung, Sammel-Chips und Exporte synchron bleiben und Inline-Follow-ups die sichtbaren Widgets vorbefüllen, statt mit `_update_profile` in Konflikt zu geraten.

EN: The customer-contact toggle in the Role & Team step now shows bilingual guidance describing when to enable it and what to capture in the follow-up details field, which itself surfaces inline hints for channels, cadence, and escalation paths.
DE: Der Kundenkontakt-Schalter im Schritt „Rolle & Team“ erklärt jetzt zweisprachig, wann er zu aktivieren ist und welche Angaben das Folgefeld benötigt; das Textfeld blendet passende Hinweise zu Kanälen, Frequenz und Eskalationen ein.
Preview / Vorschau: `images/customer_contact_toggle_preview.md` enthält eine textbasierte Darstellung des UI-Stands, da binäre Screenshots in dieser Umgebung nicht eingecheckt werden können.

EN: Step 8 (Summary) now evaluates inline follow-up questions even though it has no required fields, so “Next” stays disabled until the remaining critical prompts (for example headline or next steps) are answered before triggering exports.
DE: Schritt 8 („Summary“) prüft trotz fehlender Pflichtfelder jetzt ebenfalls die inline angezeigten Anschlussfragen, sodass „Weiter“ solange gesperrt bleibt, bis verbleibende kritische Prompts (z. B. Headline oder Next Steps) beantwortet sind und keine Exporte mehr mit offenen Klärungen starten.

EN: Uploading a second PDF or DOCX now replaces the previous extraction payload entirely and unrecoverable parsing errors (e.g., PyMuPDF/pypdf failures) surface a bilingual “Failed to extract data, please check the format” banner instead of crashing; language and dark-mode toggles persist mid-wizard without clearing captured profile data.
DE: Beim erneuten Hochladen einer PDF- oder DOCX-Datei wird der vorherige Extraktionsstand vollständig überschrieben und nicht lesbare Dateien (z. B. PyMuPDF/pypdf-Fehler) zeigen einen zweisprachigen Hinweis „Datei konnte nicht verarbeitet werden …“ statt eines Absturzes; Sprach- und Dark-Mode-Umschalter behalten mitten im Wizard alle erfassten Profildaten bei.

EN: Wizard buttons, follow-up cards, and inputs now use the shared transition tokens for hover/focus states, a brief “Next” pulse once all required data is present, and smooth scrolling when navigating so recruiters instantly see what changed.
DE: Wizard-Buttons, Follow-up-Karten und Eingabefelder nutzen nun die gemeinsamen Transition-Tokens für Hover-/Fokuszustände, einen kurzen „Weiter“-Impuls sobald alle Pflichtangaben vorliegen und ein sanftes Scrollen bei der Navigation, damit Recruiter:innen Änderungen sofort erkennen.

EN: Added a bilingual “🔄 Reset wizard” button to the sidebar settings so recruiters can instantly clear the current profile and reload the default wizard state in one click (without changing theme, language, or LLM preferences).
DE: Einen zweisprachigen Button „🔄 Zurücksetzen / Reset wizard“ in den Seiteneinstellungen hinzugefügt, mit dem Recruiter:innen das aktuelle Profil mit einem Klick entfernen und den Wizard mit Standardwerten neu laden können (ohne Dark-Mode-, Sprach- oder LLM-Einstellungen zu verändern).

EN: The Manual additions expander in the job-ad generator now shows bilingual placeholder hints (e.g., “Key achievements / wichtigste Erfolge” and “Upload a PDF or paste highlights”) so subject-matter experts immediately know how to use the optional fields.
DE: Der Bereich „Manuelle Ergänzungen“ im Stellenanzeigen-Generator enthält nun zweisprachige Platzhalter-Hinweise (z. B. „Key achievements / wichtigste Erfolge“ und „Upload a PDF or paste highlights“), damit Fachexpert:innen sofort erkennen, wie sie die optionalen Felder nutzen können.

Branding Integration / Branding-Integration

EN: The wizard now recognises employer branding assets automatically. When a career page URL is provided, Cognitive Staffing detects the company logo, dominant brand colour, and slogan, then applies them to the sidebar hero, exports, and downstream JSON (company.logo_url, company.brand_color, company.claim). The screenshot below shows an example sidebar that picked up a logo and tone-on-tone accent colour without any manual configuration.

DE: Der Wizard erkennt Employer-Branding-Assets jetzt automatisch. Sobald eine Karriereseiten-URL vorliegt, ermittelt Cognitive Staffing Logo, Hauptfarbe und Claim des Unternehmens und übernimmt sie in die Sidebar, Exporte sowie das JSON (company.logo_url, company.brand_color, company.claim). Der Screenshot unten zeigt eine Sidebar, die Logo und Akzentfarbe ohne manuelle Einstellungen übernommen hat.

EN: If detection misses assets you can open the sidebar branding settings to upload a logo or choose a fallback colour. The job-ad generator now feeds the slogan and brand colour into its prompt metadata and Markdown fallback, ensuring downstream exports keep the employer voice.

DE: Falls die Erkennung keine Assets findet, kannst du in den Branding-Einstellungen der Sidebar ein Logo hochladen oder eine Ersatzfarbe wählen. Die Stellenanzeigengenerierung übergibt Claim und Markenfarbe an Prompt-Metadaten und Markdown-Fallback, damit Exporte den Arbeitgeberton zuverlässig mitführen.

Limitations / Einschränkungen
EN: Branding detection currently targets public websites. Private portals or PDF-only uploads fall back to the default Cognitive Staffing theme.
DE: Die Branding-Erkennung funktioniert derzeit für öffentliche Websites. Private Portale oder reine PDF-Uploads nutzen weiterhin das Standard-Theme.

EN: When no brand assets are available the sidebar now surfaces a prominent “Set branding” call-to-action instead of showing placeholder slogans or demo logos.
DE: Liegen keine Brand-Assets vor, blendet die Sidebar jetzt einen gut sichtbaren „Branding setzen“-Hinweis ein und verzichtet auf Beispiel-Claims oder Demo-Logos.

What's new in v1.0.0 / Neu in v1.0.0

Wizard overhaul & schema alignment:
EN: Every wizard step now shares a consistent header/subheader/intro layout that maps one-to-one to the NeedAnalysisProfile schema, ensuring exports remain perfectly synced.
DE: Alle Wizard-Schritte nutzen jetzt ein einheitliches Header-/Subheader-/Intro-Layout mit direkter 1:1-Abbildung auf das NeedAnalysisProfile-Schema, sodass Exporte lückenlos synchron bleiben.

Multi-tone guidance for each step:
EN: New pragmatic, formal, and casual intro texts (EN/DE) explain what to capture on every step and adapt automatically to the selected language.
DE: Neue pragmatische, formelle und lockere Intro-Texte (DE/EN) erläutern pro Schritt, welche Angaben benötigt werden, und passen sich automatisch der gewählten Sprache an.

Expanded AI assistance:
EN: Skills, benefits, and responsibilities now feature refreshed AI/ESCO suggestion buttons with better error handling, while the interview step generates full guides with graceful fallbacks.
DE: Skills, Benefits und Verantwortlichkeiten erhalten aktualisierte KI-/ESCO-Vorschlagsbuttons mit robuster Fehlerbehandlung, und der Interview-Schritt erzeugt komplette Leitfäden inklusive Fallbacks.

Design system & mobile polish:
EN: Light/dark themes share one design token set with improved spacing, focus states, and responsive navigation for mobile recruiters.
DE: Light-/Dark-Themes greifen auf einen gemeinsamen Design-Token-Pool mit optimierten Abständen, Fokuszuständen und responsiver Navigation für mobile Recruiter:innen zurück.

EN: The refreshed palette keeps the navy brand anchors (#0C1F3D in dark mode / #2A4A85 in light mode) and balances them with high-contrast teal (#1FB5C5) and amber (#FFC368/#FFB65C) accents, ensuring ≥ 4.5:1 contrast for hero panels, chips, and alerts in both themes.
DE: Die aktualisierte Palette kombiniert die Navy-Anker (#0C1F3D im Dark-Mode / #2A4A85 im Light-Mode) mit kontrastreichem Teal (#1FB5C5) sowie Bernstein-Akzenten (#FFC368/#FFB65C), sodass Hero-Panels, Chips und Hinweise in beiden Themes eine Kontrast-Ratio von mindestens 4,5:1 erreichen.

EN: Global styling now loads exclusively through `inject_global_css()` (app.py) and the cognitive_needs.css/light variants, so the legacy Tailwind injector and CDN include have been removed for faster startup and fewer collisions.
DE: Das globale Styling wird ausschließlich über `inject_global_css()` (app.py) sowie die Dateien cognitive_needs.css/light geladen, sodass der frühere Tailwind-Injektor samt CDN-Einbindung entfällt – Startzeiten verkürzen sich und Stilkonflikte werden vermieden.

Employment logistics guidance / Hinweise zur Beschäftigungslogistik

EN: The employment panel toggles now include bilingual helper text that explains the policy expectation for travel, relocation, visa sponsorship, overtime, security clearance, and shift work, and it calls out when extra inputs (e.g., travel share, relocation package terms) will appear. This keeps SMEs aligned on what to capture before expanding the follow-up fields.
DE: Die Umschalter im Beschäftigungs-Panel enthalten nun zweisprachige Hilfetexte, die die Erwartungen zu Reisetätigkeit, Relocation, Visa-Sponsoring, Überstunden, Sicherheitsprüfung und Schichtarbeit erläutern und ankündigen, wann zusätzliche Eingaben (z. B. Reiseanteil oder Relocation-Konditionen) eingeblendet werden. So wissen Fachexpert:innen vorab, welche Angaben beim Öffnen der Folgefelder benötigt werden.

Compliance screening controls / Compliance-Prüfungen

EN: A dedicated “Compliance Checks” panel on the Skills & Requirements step lets recruiters mark background checks, reference calls, and portfolio submissions as mandatory with bilingual helper copy explaining what each screening covers.
DE: Ein eigenes Panel „Compliance Checks“ im Schritt Skills & Requirements erlaubt es Recruiter:innen, Hintergrund-Checks, Referenzabfragen und Portfolio-Einreichungen als verpflichtend zu markieren – inklusive zweisprachiger Hilfetexte, die den Umfang der jeweiligen Prüfung beschreiben.

EN: Those toggles now persist as the canonical schema fields `requirements.background_check_required`, `requirements.reference_check_required`, and `requirements.portfolio_required`, so downstream exports and automations can rely on them without custom mapping.
DE: Diese Umschalter werden jetzt als kanonische Schemafelder `requirements.background_check_required`, `requirements.reference_check_required` und `requirements.portfolio_required` gespeichert, sodass nachgelagerte Exporte und Automationen ohne Sonder-Mapping darauf zugreifen können.

EN: The Summary step now mirrors those compliance switches with the same bilingual helper text, so reviewers can finalize background/reference/portfolio decisions without jumping back to Skills & Requirements; any changes stay synced with exports and `ProfilePaths.REQUIREMENTS_*`.
DE: Der Summary-Schritt zeigt dieselben Compliance-Schalter inklusive zweisprachiger Hinweise, damit Reviewer:innen Hintergrund-, Referenz- und Portfolio-Pflichten direkt beim Abschluss anpassen können – Änderungen bleiben mit Exporten und `ProfilePaths.REQUIREMENTS_*` synchron.
EN: The Job Ad composer and export selector now surface those toggles inside the “Requirements” group, making it obvious in every generated posting whether background checks, reference calls, or portfolios are mandatory.
DE: Der Stellenanzeigen-Generator sowie die Export-Auswahl führen die drei Schalter jetzt im Abschnitt „Anforderungen“, damit jede veröffentlichte Anzeige klar signalisiert, ob Hintergrundprüfungen, Referenzgespräche oder Portfolios Pflicht sind.
Preview / Vorschau: `images/summary_compliance_toggles_preview.md` beschreibt die Ansicht textuell, da in diesem Repo keine Binär-Screenshots eingecheckt werden.

*EN: Screenshot temporarily removed while the repository avoids binary assets for this panel. DE: Screenshot vorübergehend entfernt, da das Repository für dieses Panel keine Binärdateien führen soll.*

Feature Highlights

Structured extraction: JSON schemas and Pydantic validation keep 20+ vacancy fields aligned with the NeedAnalysisProfile model. LangChain’s StructuredOutputParser and PydanticOutputParser are now used to embed format instructions directly into prompts and to coerce responses back into the model, reducing brittle parsing code. Locked fields such as job_title or company are auto-filled when rule matches fire and remain protected until explicitly unlocked.
EN: When schema validation still flags invalid fields, the parser now prunes those entries and the wizard surfaces a bilingual warning plus error details so recruiters can correct the impacted fields instead of seeing the profile reset to defaults.
DE: Wenn die Schema-Validierung dennoch ungültige Felder erkennt, entfernt der Parser nur diese Einträge und der Wizard zeigt eine zweisprachige Warnung samt Fehlerdetails an, damit Recruiter:innen die betroffenen Felder gezielt korrigieren können, ohne dass das Profil auf Standardwerte zurückfällt.

Interactive follow-ups: A Follow-up Question Generator agent produces prioritized follow-up questions with suggestion chips. When ESCO metadata is available, the assistant injects normalized essential skills into its prompts, and an auto re-ask loop will keep rerunning critical questions until every must-have field is answered.

ESCO integration: When enabled, the ESCO enricher normalizes job titles, proposes essential skills, and flags missing competencies directly in the UI.

Critical field safeguards / Schutz kritischer Felder:
EN: Company contact emails and the primary city hint now fall back to blank strings inside the normalized profile whenever neither extraction nor manual input supplies data, so rule checks and exports no longer warn about missing required fields.
DE: Unternehmens-Kontaktmails sowie der primäre Stadthinweis fallen im normalisierten Profil jetzt auf leere Strings zurück, wenn weder Extraktion noch manuelle Eingabe Werte liefern – dadurch verschwinden Warnungen zu fehlenden Pflichtfeldern in Regeln und Exporten.
EN: Inline follow-up cards automatically re-ask for `company.contact_email` and `location.primary_city` with bilingual prompts whenever those values remain empty, so the Company and Location steps stay blocked until recruiters provide actionable details.
DE: Inline-Follow-up-Karten fragen `company.contact_email` und `location.primary_city` jetzt automatisch mit zweisprachigen Prompts nach, sobald diese Felder leer sind – dadurch bleiben Unternehmens- und Standortschritt gesperrt, bis nutzbare Angaben vorliegen.

AI-assisted suggestions: Dedicated helper agents surface responsibilities, skills, benefits, boolean strings, interview guides, and polished job ads. Responses stream live by default so the UI remains responsive during longer generations. The requirements, role, and compensation steps now include on-demand “Suggest responsibilities”, “Suggest additional skills”, and “Suggest benefits” actions that take into account existing inputs to avoid duplicates.

Step intros & captions / Schritt-Intros & Hinweise:
EN: Each wizard page opens with a localized introductory caption (in the chosen tone) so teams immediately know which details matter most on that step.
DE: Jede Wizard-Seite startet mit einer lokalisierten Einleitung im gewählten Tonfall, damit Teams sofort wissen, welche Angaben auf diesem Schritt entscheidend sind.

Guided wizard sections / Geführte Wizard-Abschnitte:
EN: Steps are grouped into Onboarding, Company, Team & Structure, Role & Tasks, Skills & Requirements, Compensation, Hiring Process, and Summary, so recruiters can follow a consistent flow with inline help for each section. Generated follow-up questions now appear inside these sections as contextual cards, so SMEs can answer them without leaving the current page.
DE: Schritte sind in Onboarding, Unternehmen, Team & Kontext, Rolle & Aufgaben, Skills & Anforderungen, Vergütung, Prozess und Zusammenfassung gegliedert, damit Recruiter:innen einem einheitlichen Ablauf mit Inline-Hilfen pro Abschnitt folgen können. Generierte Anschlussfragen erscheinen als kontextuelle Karten direkt in den jeweiligen Abschnitten, sodass Fachexpert:innen sie beantworten können, ohne den aktuellen Schritt zu verlassen.

Tone control / Tonalitätssteuerung:
EN: Choose between concise, professional, or casual writing styles before generating job ads, interview guides, or follow-up emails.
DE: Wähle vor der Generierung von Stellenanzeigen, Interview-Guides oder Follow-up-E-Mails zwischen einem prägnanten, professionellen oder lockeren Schreibstil.

Automatic company research / Automatische Unternehmensrecherche:
EN: After uploading a job ad, the wizard fetches the company’s mission, culture, and approximate size from the web to pre-fill the company section.
DE: Nach dem Upload einer Stellenanzeige ruft der Wizard Mission, Kultur und ungefähre Unternehmensgröße aus dem Web ab und füllt den Unternehmensbereich damit vor.

Normalization & JSON repair / Normalisierung & JSON-Reparatur:
EN: A repository-wide normalization pipeline trims noise, harmonizes gender-specific terms and locations, uppercases country codes, and automatically repairs malformed profile JSON via the OpenAI Responses API if validation fails.
DE: Eine Repository-weite Normalisierung entfernt Rauschen, bereinigt Gender-Zusätze und Ortsangaben, wandelt Ländercodes in Großbuchstaben und repariert ungültiges Profil-JSON bei Validierungsfehlern automatisch über die OpenAI-Responses-API.

Branding auto-detect / Branding-Autoerkennung:
EN: Brand assets (logo, favicon, dominant color, and company claim) are scraped from provided career page URLs, cached, and injected into the wizard’s sidebar, exports, and editing forms.
DE: Branding-Assets (Logo, Favicon, dominante Farbe und Unternehmensclaim) werden von angegebenen Karriereseiten extrahiert, zwischengespeichert und in der Wizard-Sidebar, in Exporten und in den Eingabemasken angezeigt.

Analysis helpers / Analyse-Helfer:
EN: Deterministic helper tools provide salary benchmarks, currency conversion with cached FX rates, and ISO date normalization, allowing the assistant to ground certain reasoning steps without extra API calls.
DE: Deterministische Helfer liefern Gehalts-Benchmarks, Währungsumrechnung mit zwischengespeicherten FX-Kursen und ISO-Datumsnormalisierung, sodass der Assistent ohne zusätzliche APIs fundierte Herleitungen vornehmen kann.

Suggestion failover / Vorschlags-Failover:
EN: If the OpenAI Responses endpoint is unavailable or USE_CLASSIC_API=1, skill and benefit suggestions automatically fall back to the classic Chat Completions backend; persistent failures return curated static benefit shortlists so the UI never blocks.
DE: Fällt der OpenAI-Responses-Endpunkt aus oder ist USE_CLASSIC_API=1 gesetzt, weichen Skill- und Benefit-Vorschläge automatisch auf die klassische Chat-Completions-API aus; bei dauerhaften Fehlern liefern kuratierte statische Benefit-Shortlists weiterhin nutzbare Ergebnisse.

Vector-store enrichment: If you set a VECTOR_STORE_ID, the RAG agent will retrieve supporting snippets via OpenAI file_search, yielding better suggestions when the uploaded job ad is sparse on details.

Extraction cache / Extraktions-Cache:
EN: Re-uploading the same vacancy now reuses the cached structured extraction via st.cache_data, keyed by the normalized text, locked fields, and reasoning mode to avoid duplicate LLM costs.
DE: Beim erneuten Hochladen derselben Ausschreibung greift die strukturierte Extraktion auf einen st.cache_data-Cache zurück, der Text, gesperrte Felder und Reasoning-Modus berücksichtigt – doppelte LLM-Kosten entfallen.

Parallel RAG lookups / Parallele RAG-Abfragen:
EN: When a vector store is configured the field-specific file_search calls execute concurrently, so chunk retrieval completes faster even for larger schemas.
DE: Ist ein Vector-Store hinterlegt, laufen die feldspezifischen File-Search-Aufrufe parallel, wodurch die Snippet-Recherche auch bei umfangreichen Schemata schneller abgeschlossen ist.

RAG telemetry / RAG-Telemetrie:
EN: Each vector-store lookup now logs per-field latency plus fallback usage and forwards the metrics to OpenTelemetry spans, giving operators measurable evidence that the threaded retriever accelerates lookups.
DE: Jeder Vector-Store-Lookup protokolliert nun die Feldlaufzeit und ob ein Fallback greifen musste und schreibt die Messwerte in OpenTelemetry-Spans, damit Betreiber messbar nachvollziehen können, wie stark der parallelisierte Retriever die Suche beschleunigt.

Typed OTLP config / Getypte OTLP-Konfiguration:
EN: The telemetry bootstrapper now assembles an `utils.telemetry.OtlpConfig` dataclass so endpoints, headers, and timeouts are validated before creating the OTLP exporter, keeping deployments aligned across environments.
DE: Der Telemetrie-Bootstrap baut nun eine `utils.telemetry.OtlpConfig`-Dataklasse auf, sodass Endpunkte, Header und Timeouts vor dem Erstellen des OTLP-Exporters geprüft werden und Deployments in allen Umgebungen konsistent bleiben.

Multi-model routing / Modellrouting:
EN: The router now prefers gpt-4.1-mini for lightweight lookups and automatically escalates summaries, explanations, and planning flows to o4-mini, cascading through o3, gpt-4o-mini, and gpt-4o if capacity constraints occur. Administrators can still override the model via configuration (for example by setting OPENAI_MODEL), but automated selection is the default.
DE: Der Router nutzt standardmäßig gpt-4.1-mini für leichte Abfragen und hebt Zusammenfassungen, Erklärungen und Planungen auf o4-mini an, inklusive Fallbacks über o3, gpt-4o-mini und gpt-4o, sobald Kapazitätsprobleme auftreten. Administratoren können per Konfiguration (z. B. mit OPENAI_MODEL) weiterhin ein bestimmtes Modell fest vorgeben, aber normalerweise erfolgt die Modellauswahl automatisch.

Gap analysis workspace / Gap-Analyse-Arbeitsbereich:
EN: Launch the Gap analysis view to combine ESCO metadata, retrieved snippets, and vacancy text into an executive-ready report that highlights missing information and next steps.
DE: Öffne die Ansicht Gap-Analyse, um ESCO-Metadaten, gefundene Snippets und Ausschreibungstext zu einem Management-tauglichen Bericht zu kombinieren, der fehlende Informationen und nächste Schritte hervorhebt.

Model Routing & Cost Controls / Modellrouting & Kostensteuerung

Content cost router / Kostenrouter für Inhalte
EN: Each request runs through a prompt cost router that inspects the token length and content before selecting the cheapest suitable tier. Lightweight prompts execute on gpt-4.1-mini, while tasks requiring deeper reasoning automatically escalate to o4-mini. When quality risks remain high the chain continues through o3, gpt-4o-mini, and gpt-4o. Power users can still force a specific tier when necessary.
DE: Jede Anfrage durchläuft einen Kostenrouter, der Tokenlänge und Inhalt prüft, bevor das günstigste passende Modell gewählt wird. Leichte Prompts laufen auf gpt-4.1-mini, während Aufgaben mit höherem Reasoning-Bedarf automatisch auf o4-mini eskalieren. Bleiben Qualitätsrisiken bestehen, führt die Kette weiter über o3, gpt-4o-mini und gpt-4o. Bei Bedarf lässt sich weiterhin gezielt eine bestimmte Modellstufe erzwingen.

Quick vs Precise toggle / Schnell- vs. Präzisionsmodus
EN: The settings sidebar exposes a bilingual toggle to choose between the cost-efficient quick mode (minimal reasoning on gpt-4.1-mini, low verbosity) and the high-accuracy precise mode (o4-mini, high verbosity). Switching modes rewires model routing and reasoning effort automatically.
DE: In den Einstellungen gibt es nun einen zweisprachigen Schalter für den Schnellmodus (minimaler Denkaufwand auf gpt-4.1-mini, niedrige Ausführlichkeit) bzw. den Präzisionsmodus (o4-mini, hohe Ausführlichkeit). Der Wechsel passt Modellrouting und Reasoning-Aufwand automatisch an.

Fallback chain (o4-mini → o3 → GPT-4.1-nano → GPT-4o → GPT-4 → GPT-3.5) / Fallback-Kette (o4 mini → o3 → GPT-4.1 nano → GPT-4o → GPT-4 → GPT-3.5)
EN: When the primary model is overloaded or deprecated, the platform retries with the chain o4-mini → o3 → gpt-4.1-nano → gpt-4o → gpt-4 → gpt-3.5-turbo. Each downgrade is recorded in telemetry so we can spot chronic outages.
DE: Meldet die API, dass das Primärmodell überlastet oder abgekündigt ist, greift jetzt der Fallback-Pfad o4-mini → o3 → gpt-4.1-nano → gpt-4o → gpt-4 → gpt-3.5-turbo. Jeder Herunterstufungsversuch wird im Telemetrie-Stream protokolliert, um dauerhafte Störungen erkennbar zu machen.

Model override via configuration / Modell-Override über Konfiguration
EN: Use environment variables or secrets (e.g., set OPENAI_MODEL or st.session_state["model_override"]) to pin a specific model tier if necessary. Clearing the override restores automatic cost-based routing and the normal fallback chain.
DE: Setze bei Bedarf Umgebungsvariablen oder Secrets (z. B. OPENAI_MODEL oder st.session_state["model_override"]), um ein bestimmtes Modell fest vorzugeben. Ohne Override greift wieder das automatische, kostenbasierte Routing inklusive Fallback-Kette.

LLM configuration & fallbacks / LLM-Konfiguration & Fallbacks

EN:

USE_RESPONSES_API (default 1) routes all structured calls through the OpenAI Responses API with enforced JSON schemas and tool support. Setting this flag to 0 (or False) automatically toggles USE_CLASSIC_API=1 so every request uses the Chat Completions client instead.

USE_CLASSIC_API=1 forces the legacy chat backend even when Responses would normally be selected. Both suggestion and extraction pipelines retry on Responses errors first, then cascade to chat, and finally fall back to curated static copy (for example, benefit shortlists) if the API keeps failing.

RESPONSES_ALLOW_TOOLS (default 0) re-enables function/tool payloads on the Responses API. Keep the default for the 2025 Responses rollout where tool calls are blocked; set the flag to 1 only if your account is allowlisted for tool-enabled Responses. Otherwise the client automatically drops to the classic chat backend whenever tools are required.

When no OPENAI_API_KEY is configured the UI disables all AI buttons and shows a bilingual lock banner. Providing the key via environment variables or Streamlit secrets re-enables the features immediately.

REASONING_EFFORT pairs with the quick/precise toggle: quick mode enforces minimal reasoning on gpt-4.1-mini, precise mode upgrades to high effort on o4-mini, and manual overrides still cascade through the fallback chain when required.

COGNITIVE_PREFERRED_MODEL and COGNITIVE_MODEL_FALLBACKS let operators influence the router order (preferred model first, followed by comma-separated fallbacks) without code changes; legacy alias values resolve automatically.

OPENAI_BASE_URL can be set to https://eu.api.openai.com/v1 (or another allowed endpoint) to keep traffic within the EU region; other OpenAI secrets (OPENAI_MODEL, OPENAI_PROJECT, OPENAI_ORGANIZATION, OPENAI_REQUEST_TIMEOUT) are honoured as well.

VECTOR_STORE_ID activates RAG lookups through OpenAI file search. Without it the assistant skips retrieval but still completes suggestions using Responses or the chat fallback chain.

Debug panel toggle / Debug-Panel-Schalter:
EN: Administrators can use the new debug panel at the top of the wizard to enable verbose diagnostics and switch between the Responses API and the legacy Chat Completions backend at runtime; the helper keeps USE_RESPONSES_API and USE_CLASSIC_API in sync so downstream modules read the updated mode immediately.
DE: Über das neue Debug-Panel am Anfang des Wizards lassen sich ausführliche Fehlermeldungen aktivieren und die Responses- bzw. Chat-Completions-API zur Laufzeit wechseln; der Helfer hält USE_RESPONSES_API und USE_CLASSIC_API automatisch synchron, damit nachgelagerte Module den aktuellen Modus sofort übernehmen.

DE:

USE_RESPONSES_API (Standard 1) leitet strukturierte Aufrufe über die OpenAI-Responses-API mit JSON-Schema-Prüfung und Tool-Support. Wird das Flag auf 0 (oder False) gesetzt, schaltet sich automatisch USE_CLASSIC_API=1 ein und sämtliche Requests laufen über die Chat-Completions-Schnittstelle.

USE_CLASSIC_API=1 erzwingt den Legacy-Chat-Client, auch wenn Responses normalerweise gewählt würde. Vorschlags- und Extraktionspipelines versuchen zunächst Responses, wechseln danach auf Chat und greifen zuletzt auf kuratierte statische Inhalte (z. B. Benefit-Shortlists) zurück, wenn die API dauerhaft fehlschlägt.

RESPONSES_ALLOW_TOOLS (Standard 0) schaltet Funktions-/Tool-Payloads für die Responses-API wieder frei. Belasse den Standardwert für den Responses-Rollout 2025, bei dem Tools blockiert sind; setze das Flag nur auf 1, wenn dein Account für toolfähige Responses freigeschaltet wurde. Andernfalls wechselt der Client automatisch auf den klassischen Chat-Backend, sobald Tools erforderlich sind.

Ohne konfigurierten OPENAI_API_KEY deaktiviert die Oberfläche alle KI-Schaltflächen und blendet einen zweisprachigen Sperr-Hinweis ein. Sobald der Schlüssel via Umgebungsvariable oder Streamlit-Secrets hinterlegt ist, stehen die Funktionen wieder zur Verfügung.

Über REASONING_EFFORT ist der Schnell-/Präzisionsmodus gekoppelt: Der Schnellmodus setzt minimalen Denkaufwand auf gpt-4.1-mini, der Präzisionsmodus hebt auf high und o4-mini an; manuelle Overrides greifen weiterhin samt Fallback-Kette, wenn nötig.

COGNITIVE_PREFERRED_MODEL und COGNITIVE_MODEL_FALLBACKS erlauben es, die Router-Reihenfolge ohne Codeänderung zu beeinflussen (bevorzugtes Modell zuerst, gefolgt von kommaseparierten Fallbacks); historische Aliasse werden automatisch aufgelöst.

Mit OPENAI_BASE_URL lässt sich beispielsweise https://eu.api.openai.com/v1 konfigurieren, um Aufrufe innerhalb der EU zu halten; weitere OpenAI-Secrets (OPENAI_MODEL, OPENAI_PROJECT, OPENAI_ORGANIZATION, OPENAI_REQUEST_TIMEOUT) werden ebenfalls ausgewertet.

VECTOR_STORE_ID aktiviert RAG-Abfragen über OpenAI File Search. Ohne gesetzte ID überspringt der Assistent die Recherche, führt Vorschläge aber weiterhin über Responses oder die Chat-Fallback-Kette aus.

Debug-Panel-Schalter / Debug panel toggle:
DE: Über das neue Debug-Panel am Anfang des Wizards lassen sich ausführliche Fehlermeldungen aktivieren und die Responses- bzw. klassische Chat-Completions-API zur Laufzeit wechseln; der Helfer hält USE_RESPONSES_API und USE_CLASSIC_API automatisch synchron, damit nachgelagerte Module den aktuellen Modus sofort übernehmen.
EN: Administrators can use the new debug panel at the top of the wizard to enable verbose diagnostics and switch between the Responses API and the legacy Chat Completions backend at runtime; the helper keeps USE_RESPONSES_API and USE_CLASSIC_API aligned so downstream modules consume the updated mode instantly.

Architecture at a Glance

The Streamlit entry point (app.py) wires UI components from components/ and the multi-step flow in wizard.py into a shared st.session_state. Domain rules in core/ and question_logic.py keep the vacancy schema aligned with UI widgets and exports. Agents (see AGENTS.md) delegate LLM calls to llm/ helpers that return a unified ChatCallResult, manage retries, and execute any registered tools.

streamlit app.py
├─ wizard.py + components/ → builds the UI flow & session state
│   └─ wizard_tools/ → Streamlit function tools (ingest, reruns, SME merge)
├─ core/ + question_logic.py → vacancy domain logic & schema synchronization
└─ agents (AGENTS.md)
    ├─ llm/responses.py → ChatCallResult wrapper & tool runner
    │   └─ llm/rag_pipeline.py → OpenAI file_search tool (uses VECTOR_STORE_ID)
    └─ ingest/ + integrations/ → PDF/HTML/OCR loaders, ESCO API clients, vector store handlers


All LLM prompts are defined in prompts/registry.yaml and loaded via a shared prompt_registry helper, keeping the Streamlit UI and CLI utilities in sync.

Repository structure / Projektstruktur

pages/

EN: Streamlit wizard step modules named sequentially (01_… → 08_…).

DE: Streamlit-Wizard-Schritte mit fortlaufender Nummerierung (01_… bis 08_…).

wizard/

EN: Flow control, widget helpers, and routing glue for the multi-step UI.

DE: Ablaufsteuerung, Widget-Helfer und Routing-Logik für den Multi-Step-Wizard.

EN: wizard/metadata.py centralises FIELD_SECTION_MAP, CRITICAL_SECTION_ORDER, and get_missing_critical_fields so wizard.flow and wizard_router share a lightweight, circular-import-free source of truth.

DE: wizard/metadata.py bündelt FIELD_SECTION_MAP, CRITICAL_SECTION_ORDER und get_missing_critical_fields, damit wizard.flow und wizard_router eine schlanke, kreisfrei importierbare Wahrheit teilen.

core/

EN: Schema definitions, canonicalisation utilities, and business rules.

DE: Schema-Definitionen, Kanonisierung und Business-Logik.

components/

EN: Reusable Streamlit UI building blocks (cards, tables, forms).

DE: Wiederverwendbare Streamlit-Bausteine (Karten, Tabellen, Formulare).

sidebar/

EN: Sidebar orchestration including plan previews and branding settings.

DE: Sidebar-Steuerung inklusive Plan-Vorschau und Branding-Einstellungen.

EN: sidebar.__init__ imports wizard.metadata and wizard._logic during module load so cached wizard helpers stay in sync. Keep those modules free of sidebar imports (the flow engine still imports sidebar.salary) to prevent circular dependencies.

DE: sidebar.__init__ importiert wizard.metadata und wizard._logic bereits beim Laden des Moduls, damit die Wizard-Helfer ohne Wrapper verfügbar sind. Stelle sicher, dass diese Module keine Sidebar-Imports enthalten (die Flow-Engine importiert weiterhin sidebar.salary), um Kreisabhängigkeiten zu vermeiden.

state/

EN: Session-state bootstrapping and migration helpers.

DE: Initialisierung und Migration des Streamlit-Session-State.

llm/

EN: OpenAI Responses integration, routing, and tool execution helpers.

DE: Anbindung an die OpenAI-Responses-API, Routing und Tool-Ausführung.

ingest/

EN: PDF/HTML loaders, enrichment heuristics, and optional RAG connectors.

DE: PDF-/HTML-Loader, Anreicherungsheuristiken und optionale RAG-Anbindung.

exports/

EN: JSON/Markdown transformations plus downstream formatting helpers.

DE: JSON-/Markdown-Transformationen und nachgelagerte Formatierung.

docs/

EN: Extended developer and operator documentation beyond the README.

DE: Erweiterte Entwickler:innen- und Betriebsdokumentation zusätzlich zum README.

tests/

EN: Pytest suites for UI flows, schema propagation, and integrations.

DE: Pytest-Suites für UI-Flüsse, Schema-Propagation und Integrationen.

UI Binding Rules / UI-Bindungsregeln

EN:

Always get widget default values via wizard._logic.get_value(ProfilePaths.<FIELD>). The profile stored in st.session_state[StateKeys.PROFILE] is the single source of truth and already includes schema defaults.

Use canonical schema paths from constants.keys.ProfilePaths as widget keys. Avoid inventing ad-hoc session keys so the summary, follow-ups, and exports stay aligned.

Prefer the helper functions in components.widget_factory—such as text_input, select, and multiselect (re-exported in wizard.wizard)—when creating widgets. They automatically hook into _update_profile so that the sidebar, summary, and exports stay in sync.

Legacy helpers from wizard.layout have been removed; import profile widgets from components.widget_factory or the wizard.wizard re-exports instead.

Call state.ensure_state.ensure_state() early; it normalises ingestion payloads into the NeedAnalysisProfile, drops unknown keys, and seeds defaults so scraped data prefills the forms. The helper also patches known validation issues (for example, list-based interview stage counts or invalid contact emails) before falling back to a destructive reset, so partial recruiter inputs survive repair attempts.

After ingestion (via URL, PDF, or text paste), run coerce_and_fill() and normalize_profile() before rendering the form. This ensures consistent casing, whitespace, and de-duplication of lists. The normaliser returns a validated dictionary and will trigger the JSON “repair” fallback only if the cleaned payload would violate the schema.

DE:

Widget-Vorgabewerte immer über wizard._logic.get_value(ProfilePaths.<FELD>) beziehen. Die Daten in st.session_state[StateKeys.PROFILE] sind die einzige Wahrheitsquelle und enthalten bereits Schema-Defaults.

Verwende kanonische Schema-Pfade aus constants.keys.ProfilePaths als Widget-Keys. Verzichte auf spontane Session-Keys, damit Zusammenfassung, Follow-ups und Exporte synchron bleiben.

Nutze zum Rendern die Helfer in components.widget_factory (text_input, select, multiselect, auch via wizard.wizard verfügbar). Diese binden das Widget automatisch an _update_profile, sodass Sidebar, Zusammenfassung und Exporte stets synchron bleiben.

Die veralteten Helfer aus wizard.layout wurden entfernt; nutzt stattdessen components.widget_factory bzw. die Re-Exports in wizard.wizard für Profil-Widgets.

Rufe früh state.ensure_state.ensure_state() auf; dort werden Ingestion-Payloads in das NeedAnalysisProfile überführt, unbekannte Keys entfernt und Defaults gesetzt, damit Scrapes die Formulare vorbefüllen. Der Helfer behebt zudem bekannte Validierungsprobleme (z. B. Listenwerte bei Interview-Stufen oder ungültige Kontakt-E-Mails), bevor ein destruktiver Reset ausgeführt wird, sodass die bisherigen Eingaben erhalten bleiben.

Führe nach dem Import (URL, PDF oder Texteingabe) immer coerce_and_fill() und normalize_profile() aus, bevor das Formular gerendert wird. So werden Groß-/Kleinschreibung, Leerzeichen und Duplikate in Listen vereinheitlicht. Der Normalisierer liefert ein valides Dictionary und nutzt die JSON-Reparatur nur, falls das bereinigte Profil sonst gegen das Schema verstoßen würde.

Unified NeedAnalysisProfile Schema – Single Source of Truth / Einheitliches NeedAnalysisProfile-Master-Schema

EN: The unified NeedAnalysisProfile model (models/need_analysis.py) powers ingestion, the wizard, exports, and regression tests. constants/keys.ProfilePaths lists the canonical dot-paths that widget bindings, summary cards, follow-up logic, and exporters consume. core.schema.coerce_and_fill() normalises incoming payloads, applying the remaining ALIASES for backwards compatibility before validating with Pydantic. state.ensure_state.ensure_state() stores a JSON dump of the profile in st.session_state[StateKeys.PROFILE] on every run so UI panels, metadata, and exports share the same structure. Confidence metadata (such as field_confidence, high_confidence_fields, locked_fields, and rules) lives alongside the profile in StateKeys.PROFILE_METADATA, allowing the UI to highlight auto-filled fields without polluting the core schema.

DE: Das vereinheitlichte Modell NeedAnalysisProfile (models/need_analysis.py) treibt Ingestion, Wizard, Exporte und Regressionstests an. constants/keys.ProfilePaths enthält die kanonischen Dot-Pfade, die von Widgets, Zusammenfassungen, Follow-up-Logik und Exportern genutzt werden. core.schema.coerce_and_fill() normalisiert eingehende Payloads, wendet die verbliebenen ALIASES zur Rückwärtskompatibilität an und validiert anschließend mit Pydantic. state.ensure_state.ensure_state() speichert bei jedem Lauf einen JSON-Dump des Profils in st.session_state[StateKeys.PROFILE], sodass UI-Panels, Metadaten und Exporte dieselbe Struktur teilen. Confidence-Metadaten (z. B. field_confidence, high_confidence_fields, locked_fields und rules) liegen begleitend in StateKeys.PROFILE_METADATA, wodurch automatisch gefüllte Felder hervorgehoben werden können, ohne das Kernschema zu verändern.
