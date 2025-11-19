Changelog

Unreleased – Sidebar Polish / Sidebar-Feinschliff

Changed / Geändert

- EN: Tightened the job-ad, interview-guide, and follow-up question prompts so every section explicitly mirrors the structured vacancy data, uses inclusive/bias-free HR language, references the relevant schema fields (job title, seniority, work policy, etc.), and only asks for job-relevant clarifications with realistic answer suggestions.
  DE: Die Prompts für Stellenanzeigen, Interviewleitfäden und Nachfragen wurden geschärft: Alle Abschnitte spiegeln jetzt die strukturierten Vakanzdaten exakt wider, nutzen inklusive HR-Terminologie, verweisen auf die passenden Schemafelder (Jobtitel, Seniorität, Arbeitsmodell etc.) und stellen nur noch jobrelevante, realistische Rückfragen samt Antwortoptionen.

- EN: Strengthened the interview guide generator prompt so competency clusters stem from the vacancy profile, each competency powers at least one question, every list explicitly mixes technical/behavioural/cultural prompts (flagged via questions[].type), and each entry includes two evaluation criteria for consistent scoring.
  DE: Den Interview-Guide-Prompt erweitert, damit die Kompetenzcluster aus dem Vakanzprofil abgeleitet werden, jede Kompetenz mindestens eine Frage erhält, jede Liste explizit technische, verhaltensorientierte und kulturelle Fragen (gekennzeichnet über questions[].type) enthält und pro Frage zwei Bewertungskriterien für eine konsistente Beurteilung aufgeführt sind.

- EN: Standardised the bilingual labels and helper copy across all wizard steps – Company contact fields now read “Company contact email/phone”, the Team step is surfaced as “Team & Context”, hard/soft skill sections use Required/Optional wording, and the summary mirrors those terms so HR stakeholders see the same terminology end-to-end.
  DE: Zweisprachige Labels und Hilfetexte in allen Wizard-Schritten vereinheitlicht – Unternehmensfelder heißen nun „Kontakt-E-Mail (Unternehmen)“ bzw. „Kontakt-Telefon“, der Team-Schritt wird als „Team & Kontext“ angezeigt, die Hard-/Soft-Skill-Blöcke nutzen „Pflicht“ bzw. „Optional“, und die Summary spiegelt diese Begriffe für durchgängige HR-Terminologie.

- EN: Rebuilt the candidate-matching pipeline as a deterministic scorer that slashes points when must-have skills are missing, gently rewards nice-to-have coverage plus experience/location alignment, and fills the `gaps` list with the concrete qualifications a candidate lacks.
  DE: Die Kandidaten-Matching-Pipeline nutzt jetzt ein deterministisches Scoring, das fehlende Must-have-Skills massiv abwertet, Nice-to-have-Abdeckung sowie Erfahrung/Standort nur moderat belohnt und die `gaps`-Liste mit den konkret fehlenden Qualifikationen befüllt.
- EN: Candidate profile summaries now accept the vacancy requirements as context, emphasise in summary_text how the candidate aligns or diverges, and populate fit_notes with bilingual entries for match percentage, overlapping skills, and missing qualifications.
  DE: Kandidatenzusammenfassungen erhalten jetzt die Vakanzanforderungen als Kontext, beschreiben in summary_text den Fit bzw. die Abweichungen und füllen fit_notes mit zweisprachigen Einträgen zu Match-Prozent, überlappenden Skills sowie fehlenden Qualifikationen.
- EN: Hid the built-in Streamlit multi-page navigation links (app, jobad, company, …) so the custom wizard sidebar stays the only visible navigation surface; this prevents duplicate menus on the left edge of the app.
  DE: Die integrierte Streamlit-Multipage-Navigation (app, jobad, company, …) wird jetzt vollständig verborgen, damit ausschließlich die kundenspezifische Wizard-Sidebar als sichtbare Navigation dient und keine doppelten Menüs links erscheinen.
- EN: Relocated the metadata-only wizard step modules into `wizard_pages/` to disable Streamlit's default header entirely and swapped the Summary-step “captured input” chips for lightweight bullet lists so progress cues live solely in the sidebar.
  DE: Die reinen Metadaten-Schritte wurden nach `wizard_pages/` verschoben, wodurch die Streamlit-Standardleiste dauerhaft verschwindet; außerdem zeigt der Summary-Schritt erfasste Angaben nun als schlanke Aufzählung statt Chip-Reihen, sodass Fortschrittsinformationen ausschließlich in der Sidebar erscheinen.
- EN: Normalised section headers, expanders, and inline follow-up cards across Onboarding → Summary; meta follow-ups now surface inside the Onboarding extraction review tabs so the cards always appear directly beneath the fields they unblock.
  DE: Abschnittsüberschriften, Aufklapper und Inline-Follow-up-Karten wurden über alle Schritte hinweg vereinheitlicht; Meta-Follow-ups tauchen nun in den Onboarding-Extraktions-Tabs auf, sodass die Karten immer unmittelbar unter den zugehörigen Feldern angezeigt werden.

- EN: Removed the debug/API expander, captured-input chips, and the per-step progress bubbles from every wizard step so the canvas stays distraction-free while API mode switches continue to rely on the central configuration.
  DE: Das Debug-/API-Panel, die Eingabe-Chips sowie die Fortschrittsblasen wurden in allen Wizard-Schritten entfernt, damit die Oberfläche aufgeräumt bleibt – API-Umschaltungen laufen weiterhin zentral über die Konfiguration.
- EN: Unified the compliance toggles between the Skills & Requirements and Summary steps via a shared helper (same bilingual copy, single source of truth), ensured the reset button purges follow-up cards, and moved the debug/API controls into an admin-only expander that is gated by `ADMIN_DEBUG_PANEL` so the main canvas stays clean.
  DE: Die Compliance-Schalter in „Skills & Requirements“ und Summary nutzen jetzt einen gemeinsamen Helfer (identische zweisprachige Texte, zentrale State-Sync), der Zurücksetzen-Button leert die Follow-up-Karten vollständig und das Debug-/API-Panel wandert als Admin-Expander hinter das Flag `ADMIN_DEBUG_PANEL`, damit der Canvas aufgeräumt bleibt.
- EN: Generated the NeedAnalysis JSON schema from the Pydantic model and embedded it into the vacancy extraction schema so every position/department/team field remains available throughout extraction, validation, and exports without manual drift.
  DE: Das NeedAnalysis-JSON-Schema wird jetzt direkt aus dem Pydantic-Modell erzeugt und im Vacancy-Extraktionsschema wiederverwendet, damit alle Positions-/Abteilungs-/Team-Felder von der Extraktion über die Validierung bis zu den Exporten ohne manuelle Abweichungen bestehen bleiben.
- EN: Locked down every Responses JSON schema: the pipeline tests now assert `additionalProperties: false` across all nested objects and the structured Job Ad schema requires the metadata block (tone plus target audience), preventing stray keys and missing context in model outputs.
  DE: Sämtliche Responses-JSON-Schemas wurden verschärft – die Pipeline-Tests prüfen nun `additionalProperties: false` in allen verschachtelten Objekten und das strukturierte Job-Ad-Schema verlangt den Metadatenblock (Ton und Zielgruppe), sodass keine unerwarteten Felder mehr auftauchen und keine Pflichtkontexte fehlen.
- EN: Added regression tests that validate InterviewGuide JSON responses against the schema and ensure NeedAnalysis department/team aliases survive canonicalization, preventing future schema propagation regressions.
  DE: Regressionstests ergänzt, die InterviewGuide-JSON-Antworten gegen das Schema prüfen und sicherstellen, dass NeedAnalysis-Aliasfelder für Abteilung/Team die Kanonisierung überstehen, damit künftige Schema-Propagationsregressionen ausbleiben.

Fixed / Behoben

- EN: Company contact emails entered via the wizard are now validated with the same Pydantic `EmailStr` parser as the schema, so malformed addresses raise the bilingual inline error message instead of throwing a Python `TypeError` and interrupting the form.
  DE: Im Wizard eingegebene Kontakt-E-Mails werden jetzt über den gleichen Pydantic-`EmailStr`-Parser geprüft wie im Schema, sodass fehlerhafte Adressen den zweisprachigen Inline-Hinweis anzeigen, anstatt einen Python-`TypeError` zu verursachen und das Formular zu unterbrechen.

- EN: Resetting or restarting the wizard now removes every stored follow-up question plus their `fu_*` focus sentinels so the sidebar and inline cards never resurface stale prompts after a restart.
  DE: Beim Zurücksetzen oder Neustarten des Wizards werden sämtliche gespeicherten Follow-up-Fragen sowie die zugehörigen `fu_*`-Fokus-Sentinels entfernt, sodass weder Sidebar noch Inline-Karten veraltete Prompts nach einem Neustart erneut anzeigen.


- EN: Follow-up questions now update the NeedAnalysis profile exclusively through the widget return values (or `value=` defaults) instead of mutating canonical `st.session_state["<field>"]` entries after the widgets have mounted, eliminating the recurring StreamlitAPIException about immutable session keys.
  DE: Follow-up-Fragen aktualisieren das NeedAnalysis-Profil jetzt ausschließlich über die Widget-Rückgabewerte bzw. `value=`-Defaults und fassen keine kanonischen `st.session_state["<feld>"]`-Einträge mehr nach dem Rendern an – damit verschwinden die wiederkehrenden StreamlitAPIException-Meldungen zu unveränderlichen Session-Keys.

- EN: Marked `company.name` as required in the NeedAnalysis JSON schema so the OpenAI Responses API no longer rejects the profile schema with “Missing 'name'” errors and extraction outputs stay aligned with downstream validators.
  DE: `company.name` im NeedAnalysis-JSON-Schema als Pflichtfeld markiert, damit die OpenAI-Responses-API das Profil nicht mehr mit „Missing 'name'“-Fehlern ablehnt und Extraktionsergebnisse mit den nachgelagerten Validatoren synchron bleiben.

- EN: Locked the Interview Guide focus-area schema into a shared constant and added regression validation so Responses always receives the required `label` field instead of falling back to the deterministic guide.
  DE: Den Fokusbereich-Teil des Interviewleitfaden-Schemas als gemeinsame Konstante fixiert und mit einem Regressionstest abgesichert, damit Responses das Pflichtfeld `label` zuverlässig erhält und nicht mehr auf die deterministische Vorlage zurückfällt.

- EN: Corrected the Interview Guide JSON schema so the Responses API sees every top-level property (including the required `label` field) and stops returning “Missing 'label'” errors, ensuring the wizard keeps the AI-generated guide instead of falling back to the deterministic template.
  DE: Das JSON-Schema für den Interviewleitfaden wurde korrigiert, sodass die Responses-API nun alle obersten Eigenschaften (einschließlich des Pflichtfelds `label`) erkennt, keine „Missing 'label'“-Fehler mehr ausgibt und der Wizard den KI-Guide nicht länger durch die deterministische Vorlage ersetzt.
- EN: Applied the NeedAnalysis and RecruitingWizard alias dictionaries whenever payloads flow from extraction, wizard forms, or exports into the canonical models, so legacy keys like `role.department` or `company.headquarters` no longer trigger validation errors.
  DE: Die NeedAnalysis- und RecruitingWizard-Alias-Tabellen werden jetzt bei allen Payload-Transfers aus Extraktion, Wizard-Formularen oder Exporten angewendet, sodass Legacy-Schlüssel wie `role.department` oder `company.headquarters` keine Validierungsfehler mehr auslösen.
- EN: Summary exports and the Boolean search builder now canonicalize their session/mapping payloads via `coerce_and_fill()`, letting `role.department`, `role.team`, and `company.headquarters` values load without raising NeedAnalysisProfile validation errors.
  DE: Summary-Exporte und der Boolean-Suchgenerator kanonisieren ihre Session- bzw. Mapping-Payloads nun über `coerce_and_fill()`, damit Werte aus `role.department`, `role.team` und `company.headquarters` ohne NeedAnalysisProfile-Validierungsfehler geladen werden können.
- EN: Streaming completions now retry missing `response.completed` events via a non-streamed Responses call and, if necessary, a Chat Completions fallback, preventing partial outputs and noisy tracebacks in Streamlit logs.
  DE: Streaming-Antworten wiederholen fehlende `response.completed`-Events zuerst über eine nicht gestreamte Responses-Anfrage und greifen bei Bedarf auf die Chat-Completions-API zurück, wodurch Teilantworten und laute Tracebacks in den Streamlit-Logs vermieden werden.
- EN: Structured extraction now trims invalid fields from partial JSON fragments, repairs stage counts, and surfaces a bilingual warning with field-level error details whenever parsing needs recovery, so recruiters keep valid data and immediately know which inputs to fix instead of silently falling back to empty defaults.
  DE: Die strukturierte Extraktion entfernt ungültige Felder aus unvollständigen JSON-Fragmenten, korrigiert Stufenangaben und blendet bei reparierten Antworten eine zweisprachige Warnung mit Feld-Details ein, damit valide Daten erhalten bleiben und Recruiter:innen sofort wissen, welche Angaben zu korrigieren sind, statt unbemerkt auf leere Standardprofile zurückzufallen.
- EN: Every wizard step now shows a bilingual warning banner whenever extraction needed repair or fell back to defaults, reusing the structured error summary so the affected fields are listed inline for immediate manual fixes.
  DE: Jeder Wizard-Schritt blendet bei reparierter Extraktion bzw. Profil-Reset ein zweisprachiges Warnbanner ein und nutzt die strukturierte Fehlerliste, sodass die betroffenen Felder direkt sichtbar sind und sich sofort korrigieren lassen.
- EN: Recompute Company-step required fields after inline validators run so clearing the contact email or primary city immediately disables “Next” again and surfaces the bilingual warning before moving on.
  DE: Die Pflichtfeldprüfung im Unternehmensschritt läuft jetzt nach den Inline-Validatoren erneut, sodass das Löschen der Kontakt-E-Mail oder Primärstadt „Weiter“ sofort sperrt und der zweisprachige Hinweis erscheint, bevor es weitergeht.
- EN: WizardRouter now reruns the contact email and primary city validators using the latest widget state, clears stale profile values, and shows a bilingual warning beside “Next” so recruiters cannot advance while either field is empty.
  DE: WizardRouter führt die Validatoren für Kontakt-E-Mail und Primärstadt nun mit den aktuellen Widget-Werten erneut aus, leert veraltete Profilangaben und blendet neben „Weiter“ einen zweisprachigen Hinweis ein, damit keine Navigation mit leeren Feldern möglich ist.
- EN: Restored the required badges and widget-state fallbacks for the Company-step contact email and primary city inputs so reruns without widget data still keep valid values, the inline bilingual warnings stay visible, and “Next” never unlocks until both fields are filled.
  DE: Pflicht-Badges und Widget-State-Fallbacks für Kontakt-E-Mail und Primärstadt im Unternehmensschritt wurden wiederhergestellt, damit Reruns ohne Widget-Daten dennoch gültige Werte behalten, die zweisprachigen Hinweise sichtbar bleiben und „Weiter“ erst freigeschaltet wird, wenn beide Felder befüllt sind.
- EN: Company-step required fields now re-run the contact email and primary city validators whenever the page recomputes missing data, so stale widget text that was already cleared from the profile still triggers the bilingual “field required” copy and keeps “Next” disabled.
  DE: Die Pflichtfelder im Unternehmensschritt führen beim erneuten Berechnen fehlender Angaben die Validatoren für Kontakt-E-Mail und Primärstadt erneut aus, sodass zurückgebliebener Widget-Text trotz geleertem Profil weiterhin den zweisprachigen Hinweis „Dieses Feld ist erforderlich“ auslöst und „Weiter“ gesperrt bleibt.
- EN: Hardened the company contact email validator to use Pydantic's email parsing so invalid addresses surface as inline errors instead of raising a TypeError.
  DE: Die Validierung der Kontakt-E-Mail nutzt nun den Pydantic-E-Mail-Parser, damit ungültige Adressen als Inline-Fehler erscheinen und kein TypeError mehr ausgelöst wird.
- EN: Structured extraction now detects nested `process.interview_stages` validation errors, re-coerces list payloads to counts, and records a bilingual warning plus impacted field list when the profile falls back to defaults, so recruiters know what to fix instead of losing data silently.
  DE: Die strukturierte Extraktion erkennt verschachtelte Validierungsfehler bei `process.interview_stages`, wandelt Listenwerte wieder in Zähler um und speichert eine zweisprachige Warnung inklusive betroffener Felder, sobald das Profil auf Standardwerte zurückgesetzt werden muss – Recruiter:innen sehen sofort, wo nachgebessert werden muss.

v1.1.0 – Wizard Hardening & Schema Alignment / Wizard-Härtung & Schemaabgleich (2025-11-19)

Added / Neu

- EN: Introduced the bilingual debug panel plus config.set_api_mode(), letting admins switch between Responses and Chat APIs, flip RESPONSES_ALLOW_TOOLS, and stream verbose diagnostics at runtime.
  DE: Neues zweisprachiges Debug-Panel inklusive config.set_api_mode(), mit dem Admins zwischen Responses- und Chat-API umschalten, RESPONSES_ALLOW_TOOLS steuern und detaillierte Diagnosen live aktivieren können.
- EN: Added the quick vs precise routing toggle that maps to gpt-4.1-mini/minimal reasoning or o4-mini/high reasoning, reuses cached structured extractions, and parallelises vector-store lookups for faster responses.
  DE: Schnell-/Präzisionsmodus eingeführt, der gpt-4.1-mini mit minimalem Denkaufwand oder o4-mini mit hoher Reasoning-Tiefe ansteuert, strukturierte Extraktionen cached und Vector-Store-Abfragen parallelisiert.
- EN: Delivered a bilingual "🔄 Reset wizard" control plus inline follow-up cards embedded in every wizard section so SMEs can answer questions directly where data gaps surface.
  DE: Einen zweisprachigen Button „🔄 Wizard zurücksetzen“ sowie Inline-Follow-up-Karten in allen Wizard-Abschnitten ergänzt, damit Fachexpert:innen offene Fragen genau dort beantworten, wo Lücken entstehen.
- EN: The Company step now enforces `company.contact_email` and `location.primary_city` with bilingual helper text, inline validation, and navigation gating so exports always include a reachable contact and location context.
  DE: Der Unternehmensschritt verlangt jetzt `company.contact_email` und `location.primary_city` mit zweisprachigen Hilfetexten, Inline-Validierung und blockierter Navigation, damit Exporte stets einen erreichbaren Kontakt sowie Standortkontext enthalten.
- EN: Added dedicated department.* and team.* sections, requirement toggles for background/reference/portfolio checks, and a customer-contact flag so step 3 covers the full organisational context.
  DE: Eigene Abschnitte für department.* und team.*, Schalter für Background-/Referenz-/Portfolio-Prüfungen und einen Kundenkontakt-Flag ergänzt, damit Schritt 3 den gesamten organisatorischen Kontext abbildet.
- EN: Integrated LangChain StructuredOutputParser + PydanticOutputParser, PyMuPDF for PDF exports, and cache-aware extraction reuse so responses deserialize straight into NeedAnalysisProfile.
  DE: LangChains StructuredOutputParser und PydanticOutputParser sowie PyMuPDF für PDF-Exporte integriert und den Extraktions-Cache erweitert, damit Antworten direkt in NeedAnalysisProfile landen.
- EN: Added a “Compliance Checks” requirement panel so recruiters can toggle background, reference, and portfolio screenings with bilingual helper copy.
  DE: Neues Panel „Compliance Checks“ ergänzt, in dem Recruiter:innen Hintergrund-, Referenz- und Portfolio-Prüfungen per zweisprachigen Hilfetexten aktivieren können.
- EN: Promoted `requirements.background_check_required`, `.reference_check_required`, and `.portfolio_required` to first-class RecruitingWizard fields so schema propagation, exports, and downstream automations keep them in sync.
  DE: Die Felder `requirements.background_check_required`, `.reference_check_required` und `.portfolio_required` sind jetzt erstklassige RecruitingWizard-Felder, sodass Schema-Propagation, Exporte und Automationen sie ohne Drift übernehmen.
- EN: Added the compliance toggles to the Job Ad field selector (Requirements group) so generated postings and exporters can highlight screening expectations without manual copy.
  DE: Die Compliance-Schalter erscheinen nun auch im Stellenanzeigen-Feld-Selector (Bereich „Anforderungen“), sodass generierte Anzeigen und Exporte die Prüfpflichten ohne manuelle Texte hervorheben.
- EN: Mirrored the compliance toggles onto the Summary step with bilingual helper text and `_update_profile` wiring so late edits stay synchronized with `ProfilePaths.REQUIREMENTS_*` and downstream exports.
  DE: Die Compliance-Schalter erscheinen nun auch im Summary-Schritt inklusive zweisprachiger Hinweise und `_update_profile`-Sync, damit späte Anpassungen `ProfilePaths.REQUIREMENTS_*` sowie Exporte automatisch aktualisieren.

Changed / Geändert

- EN: Rebuilt the wizard as an eight-step flow (Onboarding, Company, Team, Role, Skills, Compensation, Process, Summary) with a tabbed extraction review, chip-based follow-ups, and a progress tracker that counts required plus critical schema paths.
  DE: Den Wizard als achtstufigen Ablauf (Onboarding, Unternehmen, Team, Rolle, Skills, Vergütung, Prozess, Summary) neu aufgebaut – inklusive tabbasierter Extraktionskontrolle, Chip-Follow-ups und Fortschrittsanzeige über Pflicht- und kritische Schemafelder.
- EN: Relocated the workflow progress tracker into the sidebar between the quick snapshot and step-context sections. Each step now renders as a compact expander that highlights the active stage and lists every schema key with captured data so recruiters can audit progress without leaving the canvas.
  DE: Den Workflow-Fortschrittsanzeiger in die Sidebar zwischen Schnellüberblick und Schritt-Kontext verschoben. Jeder Schritt erscheint dort als kompakter Aufklapper, markiert den aktuellen Abschnitt und listet alle bereits befüllten Schemafelder auf, damit Recruiter:innen den Fortschritt prüfen können, ohne den Canvas zu verlassen.
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
- EN: Added a `[tool.poetry]` section with `package-mode = false` and updated deployment instructions so Streamlit Cloud runs `poetry install --no-root`, ensuring local and hosted environments share the same dependency resolver.
  DE: Einen `[tool.poetry]`-Abschnitt mit `package-mode = false` ergänzt und die Deployment-Anleitung aktualisiert, damit Streamlit Cloud `poetry install --no-root` ausführt und lokale wie gehostete Umgebungen denselben Dependency-Resolver nutzen.
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

- EN: state.ensure_state() now patches known validation issues (e.g. list-based `process.interview_stages`, malformed `company.contact_email`) in place and only resets the profile when recovery fails completely, preserving recruiter input while still enforcing defaults for critical fields.
  DE: state.ensure_state() behebt bekannte Validierungsprobleme (z. B. Listenwerte bei `process.interview_stages`, ungültige `company.contact_email`) direkt im Profil und setzt nur noch im Notfall komplett zurück, sodass Recruiter:innen-Eingaben erhalten bleiben und kritische Felder trotzdem Standards erhalten.
- EN: Removed the duplicate `company.headquarters` schema field, aliased old data to `company.hq_location`, and updated the wizard summary so headquarters is stored and rendered via a single canonical key.
  DE: Das doppelte Schemafeld `company.headquarters` entfernt, Altdaten auf `company.hq_location` gemappt und die Wizard-Zusammenfassung aktualisiert, sodass der Hauptsitz nur noch über einen kanonischen Schlüssel geführt wird.
- EN: Inline follow-up prompts now automatically request `company.contact_email` and `location.primary_city` whenever those values remain blank, merging extraction-missing metadata with live profile validation so recruiters cannot proceed without actionable contact and city details. Normalization still backfills empty strings for these fields, satisfying downstream schemas without noisy warnings.
  DE: Inline-Follow-ups fragen `company.contact_email` und `location.primary_city` jetzt automatisch ab, sobald die Felder leer sind, indem Extraktions-Lücken mit der laufenden Profilvalidierung kombiniert werden – Recruiter:innen können daher nicht mehr ohne erreichbare Kontakt- oder Stadtangaben fortfahren. Die Normalisierung setzt beide Felder weiterhin auf leere Strings zurück, sodass nachgelagerte Schemas ohne Warnungen erfüllt werden.
- EN: Pressing “Next” on the Company step now re-runs the contact email and city validators against the current session state, clears stale profile data, and keeps the page in place while showing the bilingual warning beside the button so blank contact info never slips through navigation.
  DE: Beim Klick auf „Weiter“ im Unternehmensschritt laufen die Validatoren für Kontakt-E-Mail und Stadt erneut über den aktuellen Session-State, veraltete Profilwerte werden geleert und der Schritt bleibt gesperrt, während der zweisprachige Hinweis direkt am Button erscheint – so gelangen keine leeren Kontaktfelder mehr an den Folgeschritt.
- EN: Ensured schema propagation regenerates the wizard type/exports metadata so downstream exporters and validations stay aligned with the canonical headquarters field.
  DE: Die Schema-Propagation erneuert, damit Wizard-Typinformationen und Exporte wieder mit dem kanonischen Hauptsitzfeld übereinstimmen und nachgelagerte Exporte valide bleiben.
- EN: Added bilingual error boundaries around `run_wizard()` and every step renderer so parsing/Streamlit exceptions surface inline without resetting the session, and guarded `WizardRouter` bootstrap logic to stop reconnect spam when a session is already live.
  DE: Zweisprachige Fehlergrenzen rund um `run_wizard()` und alle Schritt-Renderer eingebaut, damit Parser-/Streamlit-Ausnahmen inline angezeigt werden statt die Sitzung zu beenden, und das `WizardRouter`-Bootstrap abgesichert, sodass bestehende Sitzungen nicht mehr mehrfach verbunden werden.
- EN: Ensured `company.contact_email` and `location.primary_city` always exist (defaulting to blank strings when unknown) so rule
  checks and export jobs stop emitting “required field not found” warnings.
  DE: `company.contact_email` und `location.primary_city` werden jetzt selbst bei fehlenden Eingaben als leere Strings hinterlegt,
  sodass Regelprüfungen und Exporte keine Warnung „Required field not found“ mehr anzeigen.
- EN: Hardened the NeedAnalysis JSON parser and repair helpers so LLMs that emit
  `process.interview_stages` as `[]` or `[3]` are coerced into `null` or numeric
  counts, keeping downstream validation green.
  DE: NeedAnalysis-Parser und -Reparatur erzwingen jetzt `null` bzw. numerische
  Werte, wenn LLMs `process.interview_stages` als `[]` oder `[3]` liefern, sodass
  die Validierung stabil bleibt.
- EN: The Process step now writes `process.interview_stages` as a numeric count via a dedicated number input, preventing Pydantic from receiving list payloads and rejecting parsed profiles.
  DE: Der Prozess-Schritt speichert `process.interview_stages` jetzt als numerischen Zähler über ein eigenes Nummernfeld, sodass Pydantic keine Listen mehr erhält und Profile nicht länger abgelehnt werden.
- EN: Replaced the OTLP exporter dictionary plumbing with the typed `OtlpConfig` helper so telemetry bootstrap validates endpoints, headers, and timeouts while satisfying mypy without overrides.
  DE: Die OTLP-Exporter-Konfiguration nutzt jetzt den typisierten Helper `OtlpConfig`, damit Endpunkte, Header und Timeouts vor dem Bootstrap geprüft werden und mypy ohne Overrides besteht.
- EN: Hardened inline follow-up enforcement so new critical prompts (summary headline, background-check toggles, etc.) block navigation while optional prompts remain optional, and added regression tests that jump directly to the Summary step.
  DE: Die Inline-Follow-ups sperren jetzt auch neue kritische Prompts (Summary-Headline, Background-Check-Schalter usw.) zuverlässig, während optionale Fragen freiwillig bleiben; Regressionstests decken den direkten Sprung zum Summary-Schritt ab.
- EN: Synced the Role/Skills/Benefits/Process page metadata with the canonical ProfilePaths entries and prefilled widget state whenever inline follow-ups answer those fields, eliminating `_update_profile` races and keeping required-field gating plus summary chips in lockstep with the UI.
  DE: Die Metadaten der Schritte Rolle/Skills/Benefits/Prozess greifen nun auf die kanonischen ProfilePaths zu und Inline-Follow-ups befüllen die entsprechenden Widgets vor, wodurch `_update_profile`-Kollisionen verschwinden und Pflichtfeldprüfung sowie Summary-Chips exakt mit der UI übereinstimmen.
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
- EN: Added bilingual follow-up widget guidance to `docs/DEV_GUIDE.md`, covering `st.session_state[f"fu_{<schema_path>}"]`, `_sync_followup_completion`, and sidebar clearing expectations.
  DE: Zweisprachige Follow-up-Widget-Anleitung in `docs/DEV_GUIDE.md` ergänzt – inklusive `st.session_state[f"fu_{<schema_path>}"]`, `_sync_followup_completion` und Vorgaben zum Bereinigen der Sidebar.
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

fix: preserve NeedAnalysis alias fields (department/team) prior to validation so HR data is not pruned

Fix: NeedAnalysis-Aliasfelder (Department/Team) vor der Validierung bewahren, damit HR-Daten nicht entfernt werden
