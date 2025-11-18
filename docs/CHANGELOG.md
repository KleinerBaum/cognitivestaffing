Changelog
v1.1.0 – Wizard Hardening & Schema Alignment / Wizard-Härtung & Schemaabgleich (2025-11-19)

Added / Neu

- EN: Introduced the bilingual debug panel plus config.set_api_mode(), letting admins switch between Responses and Chat APIs, flip RESPONSES_ALLOW_TOOLS, and stream verbose diagnostics at runtime.
  DE: Neues zweisprachiges Debug-Panel inklusive config.set_api_mode(), mit dem Admins zwischen Responses- und Chat-API umschalten, RESPONSES_ALLOW_TOOLS steuern und detaillierte Diagnosen live aktivieren können.
- EN: Added the quick vs precise routing toggle that maps to gpt-4.1-mini/minimal reasoning or o4-mini/high reasoning, reuses cached structured extractions, and parallelises vector-store lookups for faster responses.
  DE: Schnell-/Präzisionsmodus eingeführt, der gpt-4.1-mini mit minimalem Denkaufwand oder o4-mini mit hoher Reasoning-Tiefe ansteuert, strukturierte Extraktionen cached und Vector-Store-Abfragen parallelisiert.
- EN: Delivered a bilingual "🔄 Reset wizard" control plus inline follow-up cards embedded in every wizard section so SMEs can answer questions directly where data gaps surface.
  DE: Einen zweisprachigen Button „🔄 Wizard zurücksetzen“ sowie Inline-Follow-up-Karten in allen Wizard-Abschnitten ergänzt, damit Fachexpert:innen offene Fragen genau dort beantworten, wo Lücken entstehen.
- EN: Added dedicated department.* and team.* sections, requirement toggles for background/reference/portfolio checks, and a customer-contact flag so step 3 covers the full organisational context.
  DE: Eigene Abschnitte für department.* und team.*, Schalter für Background-/Referenz-/Portfolio-Prüfungen und einen Kundenkontakt-Flag ergänzt, damit Schritt 3 den gesamten organisatorischen Kontext abbildet.
- EN: Integrated LangChain StructuredOutputParser + PydanticOutputParser, PyMuPDF for PDF exports, and cache-aware extraction reuse so responses deserialize straight into NeedAnalysisProfile.
  DE: LangChains StructuredOutputParser und PydanticOutputParser sowie PyMuPDF für PDF-Exporte integriert und den Extraktions-Cache erweitert, damit Antworten direkt in NeedAnalysisProfile landen.
- EN: Added a “Compliance Checks” requirement panel so recruiters can toggle background, reference, and portfolio screenings with bilingual helper copy.
  DE: Neues Panel „Compliance Checks“ ergänzt, in dem Recruiter:innen Hintergrund-, Referenz- und Portfolio-Prüfungen per zweisprachigen Hilfetexten aktivieren können.

Changed / Geändert

- EN: Rebuilt the wizard as an eight-step flow (Onboarding, Company, Team, Role, Skills, Compensation, Process, Summary) with a tabbed extraction review, chip-based follow-ups, and a progress tracker that counts required plus critical schema paths.
  DE: Den Wizard als achtstufigen Ablauf (Onboarding, Unternehmen, Team, Rolle, Skills, Vergütung, Prozess, Summary) neu aufgebaut – inklusive tabbasierter Extraktionskontrolle, Chip-Follow-ups und Fortschrittsanzeige über Pflicht- und kritische Schemafelder.
- EN: Retired the legacy `wizard.runner` module by renaming it to `wizard.flow` so navigation code clearly routes through `WizardRouter` and downstream imports avoid the circular stubs used in tests.
  DE: Das frühere Modul `wizard.runner` wurde in `wizard.flow` umbenannt, sodass klar ersichtlich ist, dass die Navigation über `WizardRouter` läuft und nachgelagerte Importe ohne die bisher notwendigen Test-Stubs auskommen.
- EN: Wizard navigation, follow-up cards, and Streamlit inputs now animate with the shared transition tokens (box-shadow hover states, “Next” pulse, smooth scroll to top) so state changes are obvious without feeling distracting.
  DE: Wizard-Navigation, Follow-up-Karten und Streamlit-Eingaben animieren nun mit den gemeinsamen Transition-Tokens (Box-Shadow-Hover, „Weiter“-Impuls, weiches Scrollen nach oben), damit Zustandswechsel auffallen ohne zu stören.
- EN: Salary insights now auto-trigger when job title and location hints exist, highlight required fields, summarise top drivers, plot Plotly charts, and fall back to curated benefit lists if AI output is missing.
  DE: Gehaltseinblicke starten automatisch bei Jobtitel plus Standorthinweis, listen Pflichtfelder, fassen die wichtigsten Treiber zusammen, visualisieren sie mit Plotly und greifen bei fehlenden KI-Antworten auf kuratierte Benefit-Listen zurück.
- EN: Summary, onboarding, and sidebar layouts gained a branded hero banner, compact CTA, three-tab summary (Profile, Insights, Export), Aurora-Fjord palette, and repositioned benefit modules for clearer navigation.
  DE: Summary-, Onboarding- und Sidebar-Layouts erhielten ein gebrandetes Hero-Banner, kompakte CTAs, die dreigeteilte Zusammenfassung („Profil“, „Insights“, „Export“), die Aurora-Fjord-Farbpalette und neu platzierte Benefit-Module für bessere Orientierung.
- EN: Updated both Streamlit themes with the modern navy/teal/amber palette (#0C1F3D / #2A4A85 brand anchors, #1FB5C5 teal, #FFC368/#FFB65C amber) plus lighter panels so every badge, chip, and CTA meets WCAG AA contrast in dark and light mode.
  DE: Beide Streamlit-Themes erhielten die moderne Navy-/Teal-/Bernstein-Palette (Brand-Anker #0C1F3D / #2A4A85, Teal #1FB5C5, Bernstein #FFC368/#FFB65C) sowie hellere Panels, damit Badges, Chips und CTAs in Dark- wie Light-Mode die WCAG-AA-Kontraste einhalten.
- EN: Removed the unused Tailwind injector utility and CDN include now that `inject_global_css()` applies the cognitive_needs.css/light design-system styles globally.
  DE: Den obsoleten Tailwind-Injektor samt CDN-Einbindung entfernt, da `inject_global_css()` die Design-System-Styles cognitive_needs.css/light inzwischen global bereitstellt.
- EN: Wizard metadata moved to wizard/metadata.py, ProfilePaths became the single key source across wizard/state/exports, and company web enrichment now routes through _update_profile for immediate UI sync.
  DE: Wizard-Metadaten wohnen jetzt in wizard/metadata.py, ProfilePaths fungiert als alleinige Schlüsselquelle für Wizard/State/Exporte und Web-Anreicherungen laufen über _update_profile, damit UI und Sidebar sofort aktualisieren.
- EN: Renamed every OpenAI helper argument from max_tokens to max_completion_tokens and normalised routing overrides plus dependency manifests (pyproject-only installs, ingest extras, pip install .[dev]).
  DE: Alle OpenAI-Helfer von max_tokens auf max_completion_tokens umgestellt und Routing-Overrides sowie Abhängigkeitsmanifeste vereinheitlicht (nur pyproject, ingest-Extras, pip install .[dev]).
- EN: Consolidated the dependency footprint (removed requirements.txt, slimmed default extras, added EU base URL guidance, enforced openai>=1.30.0) and set an 88 % coverage floor with coverage artifact uploads.
  DE: Abhängigkeits-Footprint konsolidiert (requirements.txt entfernt, Default-Extras verschlankt, EU-Endpoint-Doku ergänzt, openai>=1.30.0 erzwungen) und eine 88 %-Coverage-Untergrenze samt Coverage-Artefakten eingeführt.
- EN: Refined layout pieces – Summary job-ad creator with collapsible preferences, JSON export at the bottom, skill market fallback captions clarifying missing benchmarks, and navigation cleanup removing redundant links.
  DE: Layoutteile verfeinert – Stellenanzeigen-Generator mit einklappbaren Präferenzen, JSON-Export am Ende, erklärende Skill-Market-Fallbacks und bereinigte Navigation ohne redundante Links.
- EN: Employment panel toggles now display bilingual helper text describing policy expectations and when related follow-up inputs (travel share, relocation terms) will appear.
  DE: Die Umschalter im Beschäftigungs-Panel zeigen nun zweisprachige Hilfetexte, die Policy-Erwartungen sowie das Einblenden der zugehörigen Folgefelder (Reiseanteil, Relocation-Konditionen) erklären.
- EN: Added bilingual helper text plus inline hints for the customer-contact toggle and follow-up details area so recruiters know when to enable it and what to capture (channels, cadence, escalation paths).
  DE: Zweisprachige Hilfetexte samt Inline-Hinweisen für den Kundenkontakt-Schalter und das Folgefeld ergänzt, damit Recruiter:innen wissen, wann er aktiv ist und welche Angaben (Kanäle, Frequenz, Eskalationen) erwartet werden.
  Assets: `images/customer_contact_toggle_preview.md` now captures a text-only mockup of the helper copy because binary screenshots are unsupported in this environment.

Fixed / Behoben

- EN: Replaced the OTLP exporter dictionary plumbing with the typed `OtlpConfig` helper so telemetry bootstrap validates endpoints, headers, and timeouts while satisfying mypy without overrides.
  DE: Die OTLP-Exporter-Konfiguration nutzt jetzt den typisierten Helper `OtlpConfig`, damit Endpunkte, Header und Timeouts vor dem Bootstrap geprüft werden und mypy ohne Overrides besteht.
- EN: Hardened inline follow-up enforcement so new critical prompts (summary headline, background-check toggles, etc.) block navigation while optional prompts remain optional, and added regression tests that jump directly to the Summary step.
  DE: Die Inline-Follow-ups sperren jetzt auch neue kritische Prompts (Summary-Headline, Background-Check-Schalter usw.) zuverlässig, während optionale Fragen freiwillig bleiben; Regressionstests decken den direkten Sprung zum Summary-Schritt ab.
- EN: Uploading another PDF/DOCX now clears the previous extraction payload and unreadable files raise a bilingual “Failed to extract data, please check the format” banner instead of crashing mid-onboarding.
  DE: Beim erneuten Hochladen einer PDF-/DOCX-Datei wird der vorherige Extraktionsstand entfernt und nicht lesbare Dateien lösen einen zweisprachigen Hinweis „Datei konnte nicht verarbeitet werden, bitte Format prüfen“ aus, anstatt den Onboarding-Schritt abzubrechen.
- EN: Preserved the wizard reset preferences so language, reasoning mode, and dark-mode toggles remain on the user’s selections after clearing session data.
  DE: Wizard-Reset behält nun Sprach-, Reasoning- und Dark-Mode-Schalter bei, sodass die gewählten Optionen nach dem Sitzungs-Reset erhalten bleiben.
- EN: Closed the Interview Guide Responses schema with additionalProperties: false, hardened benefit suggestions by cascading Responses → Chat → curated copy, and added regression tests for phone/URL normalisation.
  DE: Interview-Guide-Responses-Schema mit additionalProperties: false abgedichtet, Benefit-Vorschläge mit Responses → Chat → kuratierter Kopie robuster gemacht und Regressionstests für Telefon-/URL-Normalisierung ergänzt.
- EN: Prevented ESCO placeholder URIs and Rheinbahn-specific heuristics from hitting live APIs unnecessarily by serving cached essentials and structured parsing with confidence metadata.
  DE: ESCO-Platzhalter-URIs sowie Rheinbahn-Heuristiken greifen nun auf gecachte Essentials und strukturierte Parser mit Confidence-Metadaten zurück, damit keine unnötigen Live-Calls entstehen.
- EN: Eliminated duplicate Streamlit widget keys for branding uploads, hardened optional profile URL sanitation, downgraded noisy rule-matcher logs, and scrubbed the final Wizard v1 scaffolding including deprecated helpers.
  DE: Doppelte Streamlit-Widget-Keys bei Branding-Uploads beseitigt, optionale Profil-URLs weiter gehärtet, laute Regelabgleich-Logs entschärft und die letzten Wizard-v1-Reste inklusive veralteter Helper entfernt.

Docs / Doku

- EN: Refreshed README, developer guide, key registry, telemetry, and JSON pipeline docs with the updated eight-step flow, repository layout, and schema alignment guidance in English and German.
  DE: README, Developer-Guide, Key-Registry, Telemetrie- sowie JSON-Pipeline-Doku mit dem aktualisierten Acht-Schritte-Flow, der Projektstruktur und Schema-Hinweisen zweisprachig überarbeitet.
- EN: Documented OpenAI configuration pathways (env vars, Streamlit secrets, EU base URL, RESPONSES_ALLOW_TOOLS) plus localization and schema propagation guardrails for contributors.
  DE: OpenAI-Konfigurationswege (Env-Vars, Streamlit-Secrets, EU-Endpunkt, RESPONSES_ALLOW_TOOLS) sowie Lokalisierungs- und Schema-Propagation-Vorgaben für Contributor:innen dokumentiert.
- EN: Documented the employment panel helper text update directly in README without shipping a binary screenshot.
  DE: Die Aktualisierung der Hilfetexte im Beschäftigungs-Panel direkt in der README dokumentiert, ohne einen binären Screenshot beizulegen.
  EN: Added a textual customer-contact helper preview under `images/customer_contact_toggle_preview.md` so reviewers can inspect the UI copy without binary artifacts; README references the file explicitly.
  DE: Eine textuelle Kundenkontakt-Vorschau unter `images/customer_contact_toggle_preview.md` ergänzt, damit Reviewer:innen die UI-Texte ohne Binärartefakte prüfen können; README verweist nun explizit darauf.

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

fix: add bilingual placeholder hints to the job-ad manual additions expander so SMEs see example titles and text guidance

Fix: Zweisprachige Platzhalter-Hinweise für den Bereich „Manuelle Ergänzungen“ hinzugefügt, damit Fachexpert:innen Beispieltitel und Texthinweise sehen
