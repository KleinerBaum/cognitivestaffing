Changelog

## [Unreleased]

- EN: Replaced static missing-field banners with a bilingual ChatKit follow-up
  assistant that asks for critical NeedAnalysisProfile fields in-context and
  writes answers into the wizard in real time (manual forms remain available
  via an expander).
  DE: Statt statischer Fehlermeldungen führt nun ein zweisprachiger ChatKit-
  Assistent durch die fehlenden Pflichtfelder, fragt diese Schritt für Schritt
  ab und überträgt die Antworten direkt ins Profil (manuelle Formulare bleiben
  über einen Aufklapper verfügbar).

- EN: Split the wizard's Company and Team steps into dedicated modules
  (`wizard/steps/company_step.py`, `wizard/steps/team_step.py`) so
  `wizard/flow.py` remains lean and step-specific changes stay isolated.
  DE: Die Wizard-Schritte Unternehmen und Team in eigene Module ausgelagert
  (`wizard/steps/company_step.py`, `wizard/steps/team_step.py`), damit
  `wizard/flow.py` schlank bleibt und schrittbezogene Anpassungen getrennt
  bleiben.

- EN: Added `core.schema_registry.load_need_analysis_schema()` as the single
  access point for the NeedAnalysis JSON schema so CLI tools, prompts, and
  repair flows all use the generated Pydantic schema instead of reading the
  file separately.
  DE: `core.schema_registry.load_need_analysis_schema()` als zentrale
  Zugriffsstelle für das NeedAnalysis-JSON-Schema ergänzt, damit CLI-Tools,
  Prompts und Repair-Flows das generierte Pydantic-Schema nutzen, statt die
  Datei separat einzulesen.

- EN: Prompted the extractor to actively capture benefits/perks sections (e.g., "Benefits", "Wir bieten", "Unser Angebot") into compensation.benefits and expanded heading detectors to stop at perks blocks.
  DE: Der Extraktor achtet nun gezielt auf Benefits-/Perk-Abschnitte (z. B. „Benefits“, „Wir bieten“, „Unser Angebot“) und schreibt sie in compensation.benefits; die Heading-Erkennung bricht bei Perk-Blöcken korrekt ab.

- EN: Company introductions from job ads (e.g., "About us" blurbs) are now summarised into `company.description` and the industry is captured in `company.industry` when evidence exists, leaving both blank when the ad is silent.
  DE: Unternehmensvorstellungen aus Stellenanzeigen (z. B. „Über uns“-Abschnitte) werden jetzt in `company.description` zusammengefasst und die Branche in `company.industry` eingetragen, sofern Hinweise vorhanden sind; andernfalls bleiben beide Felder leer.

- EN: Converted `process.hiring_process` into an ordered list of stages across schema, prompts, heuristics, UI, and exports, and added a bilingual planner assistant in the Process step that proposes seniority-aware stages and saves the confirmed sequence.
  DE: `process.hiring_process` als geordnete Schrittliste in Schema, Prompts, Heuristiken, UI und Export umgestellt und einen zweisprachigen Planer im Prozess-Schritt ergänzt, der je nach Seniorität passende Stufen vorschlägt und die bestätigte Reihenfolge speichert.

- EN: Honoured the USE_RESPONSES_API / USE_CLASSIC_API toggles, kept RESPONSES_ALLOW_TOOLS in sync for tool payload fallbacks, refreshed routing defaults to `gpt-4.1-mini` (quick) and `o4-mini`/`o3` (precise via REASONING_EFFORT), and added EU base URL + tier override env vars for OpenAI calls.
  DE: USE_RESPONSES_API-/USE_CLASSIC_API-Schalter wieder strikt beachtet, RESPONSES_ALLOW_TOOLS für Tool-Fallbacks synchronisiert, Routing-Defaults auf `gpt-4.1-mini` (Schnell) sowie `o4-mini`/`o3` (Genau via REASONING_EFFORT) aktualisiert und EU-Basis-URL plus Tier-Overrides als OpenAI-Env-Vars ergänzt.

- EN: Auto-classify extracted requirements into hard/soft skills, tools & technologies, languages, and certifications using ESCO-aware heuristics so the requirements section is consistently populated.
  DE: Extrahierte Anforderungen werden jetzt ESCO-gestützt in Hard-/Soft-Skills, Tools/Technologien, Sprachen und Zertifizierungen eingeordnet, damit der Requirements-Abschnitt zuverlässig befüllt wird.

- EN: Expanded heading synonyms (e.g., "Ihre Aufgaben", "Your Tasks", "Was Sie mitbringen") so German/English job ads map tasks and requirements into the right NeedAnalysis fields during extraction.
  DE: Heading-Synonyme erweitert (z. B. „Ihre Aufgaben“, „Your Tasks“, „Was Sie mitbringen“), damit deutsche/englische Stellenanzeigen Aufgaben und Anforderungen korrekt in die NeedAnalysis-Felder einsortieren.

- EN: Gave hidden Streamlit inputs non-empty, bilingual labels (kept visually collapsed) to remove empty-label warnings and improve accessibility.
  DE: Verdeckte Streamlit-Eingaben mit nicht-leeren, zweisprachigen Labels versehen (optisch eingeklappt), um leere-Label-Warnungen zu entfernen und die Zugänglichkeit zu verbessern.

- EN: Added a built-in prompt generator pre-commit hook that converts staged
  diffs into Codex-ready JSON payloads and stores them under
  `.tooling/out_prompts/`.
  DE: Eingebauten Prompt-Generator-Pre-Commit-Hook ergänzt, der gestagte Diffs
  in Codex-taugliche JSON-Payloads umwandelt und unter `.tooling/out_prompts/`
  ablegt.
- EN: Separated the need-analysis extraction pipeline from Streamlit UI code via `pipelines.need_analysis.extract_need_analysis_profile`, making the LLM orchestration reusable beyond the wizard.
  DE: Die Need-Analysis-Extraktion über `pipelines.need_analysis.extract_need_analysis_profile` vom Streamlit-UI-Code entkoppelt, sodass die LLM-Orchestrierung auch außerhalb des Wizards wiederverwendbar ist.
- EN: Migrated default LLM routing to `gpt-5.1` for precise mode, kept
  `gpt-4o-mini` for quick paths, removed deprecated `strict` flags from
  Responses payloads, and added a fallback test ensuring Chat completions catch
  Responses 400 errors.
  DE: Standard-LLM-Routing auf `gpt-5.1` für den Modus „Genau“ umgestellt,
  `gpt-4o-mini` für „Schnell“ beibehalten, veraltete `strict`-Flags aus
  Responses-Payloads entfernt und einen Fallback-Test ergänzt, der Chat-
  Completions bei Responses-400-Fehlern absichert.
- EN: Hardened Responses → Chat fallback handling so quick and precise flows
  both yield normalized `NeedAnalysisProfile` JSON, and added regression tests
  to compare schema outputs across API modes.
  DE: Responses-→-Chat-Fallback robuster gestaltet, damit Schnell- und Genau-
  Modus gleichermaßen normalisiertes `NeedAnalysisProfile`-JSON liefern, und
  Regressionstests ergänzt, die Schema-Ausgaben über beide API-Modi hinweg
  vergleichen.
- EN: Filled missing NeedAnalysis required fields with neutral defaults and
  normalized schema-required list entries so extraction payloads stay valid and
  follow-ups can highlight gaps.
  DE: Fehlende Pflichtfelder des NeedAnalysis-Schemas werden jetzt mit neutralen
  Platzhaltern ergänzt und schema-pflichtige Listeneinträge normalisiert, damit
  Extraktions-Payloads gültig bleiben und Follow-ups Lücken zuverlässig
  anzeigen.

## [1.1.2] - 2025-12-01

- EN: Added clearer README guidance on setup, Quick vs. Precise routing, and Responses vs. Chat API toggles so users can start the Streamlit wizard with the right model settings.
  DE: README um klarere Hinweise zu Setup, Schnell-/Präzisionsmodus und Responses- vs. Chat-API-Schaltern ergänzt, damit Nutzer:innen den Streamlit-Wizard mit den richtigen Modelleinstellungen starten.

- EN: Introduced a CONTRIBUTING guide that summarizes coding standards (PEP 8, typing), required checks (ruff, mypy, pytest), and the feature-branch workflow toward `dev`.
  DE: CONTRIBUTING-Guide ergänzt mit Coding-Standards (PEP 8, Typing), Pflicht-Checks (ruff, mypy, pytest) und Feature-Branch-Workflow Richtung `dev`.

- EN: Documented troubleshooting for invalid JSON, OpenAI errors/rate limits, EU endpoint routing, and language limitations; clarified that extraction works best on German/English job ads.
  DE: Troubleshooting zu ungültigem JSON, OpenAI-Fehlern/Rate-Limits, EU-Endpunkt und Sprachgrenzen dokumentiert; klargestellt, dass die Extraktion auf deutschen/englischen Anzeigen am besten funktioniert.

- EN: Added inline comments in `llm/client.py` to describe the Responses → Chat retry cascade that protects streaming fallbacks.
  DE: Inline-Kommentare in `llm/client.py` ergänzt, die die Responses-→-Chat-Retry-Kaskade für Streaming-Fallbacks erläutern.

- EN: Bug fix – ensured the fallback to Chat completions runs when Responses streaming returns empty content, keeping extraction results available.
  DE: Bugfix – Fallback zu Chat-Completions aktiv, wenn Responses-Streaming leere Inhalte liefert, damit Extraktionsergebnisse verfügbar bleiben.

- EN: Improvement – documented that German sections like "Rolle & Aufgaben" are parsed more reliably during extraction.
  DE: Verbesserung – festgehalten, dass deutsche Abschnitte wie „Rolle & Aufgaben“ verlässlicher extrahiert werden.

- EN: Refactor – clarified wizard navigation concepts in documentation (no functional change) while keeping the existing navigation controller layout intact.
  DE: Refactor – Wizard-Navigation in der Dokumentation präzisiert (keine Funktionsänderung), bestehender Navigationsaufbau bleibt erhalten.

## [1.1.1] - 2025-11-22

- EN: Initialised the strict-format extraction session keys (UI + backend) up front to stop Streamlit errors when toggling the checkbox in the onboarding settings.
  DE: Strict-Format-Sitzungsschlüssel (UI + Backend) vorab initialisiert, damit beim Umschalten der Checkbox in den Onboarding-Einstellungen keine Streamlit-Fehler mehr auftreten.

- EN: Removed unsupported JSON-schema keywords from OpenAI payloads so schema validation no longer rejects the extractor responses.
  DE: Nicht unterstützte JSON-Schema-Schlüssel aus OpenAI-Payloads entfernt, damit die Schema-Validierung Extraktor-Antworten nicht mehr ablehnt.

- EN: Improved German job-ad parsing by recognising headings such as "Jobbeschreibung"/"Tätigkeitsbeschreibung" and stopping requirements capture when benefits headers like "Wir bieten" appear.
  DE: Parsing deutscher Stellenanzeigen verbessert, indem Überschriften wie „Jobbeschreibung“/„Tätigkeitsbeschreibung“ erkannt und die Anforderungen gestoppt werden, sobald Benefit-Header wie „Wir bieten“ auftauchen.

- EN: Enhanced skill extraction to keep hard skills, soft skills, tools, and languages in their respective required/optional buckets for clearer downstream mapping.
  DE: Skill-Extraktion verbessert, damit Hard Skills, Soft Skills, Tools und Sprachen sauber in den jeweiligen Pflicht-/Optional-Buckets landen und nachgelagerte Mappings eindeutiger bleiben.

Unreleased – Sidebar Polish / Sidebar-Feinschliff

Changed / Geändert

- EN: Fixed the onboarding job-ad step so ISO start dates from extracted profiles are parsed into dates before rendering the picker, preventing Streamlit crashes.
  DE: Onboarding-Jobad-Schritt korrigiert: ISO-Startdaten aus extrahierten Profilen werden vor dem Rendering geparst, sodass der Date-Picker nicht mehr abstürzt.

- EN: Added a safety net when Responses streaming ends without a `response.completed` event or empty content, logging the issue and retrying via Chat completions so extraction results still populate.
  DE: Sicherheitsnetz ergänzt: Wenn Responses-Streaming ohne `response.completed`-Event oder mit leerem Inhalt endet, wird ein Hinweis geloggt und die Anfrage per Chat-Completions erneut gestellt, damit Extraktionsergebnisse weiterhin erscheinen.

- EN: Documented schema gaps from sample job ads (benefits capture, role summaries, hiring contacts) in `docs/schema_gap_analysis.md` and outlined next steps.
  DE: Schema-Lücken aus Beispiel-Stellenanzeigen (Benefits, Rollenübersicht, Kontaktzuordnung) in `docs/schema_gap_analysis.md` dokumentiert und nächste Schritte skizziert.

- EN: Split normalization utilities into focused geo/contact/profile modules, centralised the TypedDict payloads, and added
  module-level tests to guard behaviour after the refactor.
  DE: Normalisierungs-Helfer in Geo-/Kontakt-/Profil-Module aufgeteilt, die TypedDict-Payloads zentralisiert und modulbezogene
  Tests ergänzt, um das Verhalten nach dem Refactor abzusichern.

- EN: Split wizard navigation into dedicated controller (`wizard/navigation_controller.py`), UI helpers (`wizard/navigation_ui.py`), and routing-free validation utilities (`wizard/validation.py`) so session/query sync, rendering, and checks stay decoupled. Updated navigation tests to target the new seams.
  DE: Die Wizard-Navigation wurde aufgeteilt: Controller (`wizard/navigation_controller.py`) für Status/Query-Sync, UI-Helfer (`wizard/navigation_ui.py`) für das Rendering und Validierungshelfer (`wizard/validation.py`) ohne Routing-Abhängigkeit. Die Navigationstests wurden auf die neuen Schnittstellen angepasst.

- EN: Documented the wizard navigation flow and bound `WizardRouter` summary labels to the `WIZARD_PAGES` order so reordering steps updates navigation automatically.
  DE: Die Wizard-Navigation dokumentiert und die `WizardRouter`-Summary-Beschriftungen an die `WIZARD_PAGES`-Reihenfolge gekoppelt, damit Umreihungen die Navigation automatisch mitziehen.

- EN: Relaxed the need-analysis JSON schema so optional sections (department/team, process details, salary breakdowns) no longer fail validation when absent; only core fields like company name and job title stay required.
  DE: Need-Analysis-JSON-Schema gelockert, damit optionale Abschnitte (Abteilung/Team, Prozessdetails, Gehaltsangaben) ohne Werte die Validierung nicht mehr blockieren; nur Kernfelder wie Firmenname und Jobtitel bleiben verpflichtend.

- EN: Prevented strict JSON-schema streaming requests from failing when the Responses API omits the final `response.completed` event by automatically retrying the call without streaming.
  DE: Verhindert, dass strikte JSON-Schema-Streams fehlschlagen, wenn das Responses-API das abschließende `response.completed`-Event auslässt, indem der Aufruf automatisch ohne Streaming wiederholt wird.

- EN: Hardened Responses-to-Chat fallbacks so timeouts or API errors are caught, logged, and retried via classic chat completions without crashing the UI.
  DE: Responses-zu-Chat-Fallbacks robuster gemacht, damit Timeouts oder API-Fehler abgefangen, protokolliert und über klassische Chat-Completions erneut versucht werden, ohne dass die UI abstürzt.

- EN: Gave the "Direct reports" input in the Team step its own labeled row to avoid cramped layout and keep the value easy to read and edit.
  DE: Dem Feld „Direkte Reports“ im Team-Schritt eine eigene beschriftete Zeile gegeben, damit das Layout luftiger ist und der Wert gut lesbar bleibt.

- EN: Added graceful handling for OpenAI API and JSON parsing errors so Responses calls fall back to Chat completions with a logged warning instead of breaking the wizard flow.
  DE: Sanftes Fehlerhandling für OpenAI-API- und JSON-Parsing-Fehler ergänzt, sodass Responses-Aufrufe mit Warnlog auf Chat-Completions zurückfallen, ohne den Wizard-Fluss zu unterbrechen.

- EN: Captured schema-validation gaps (for example missing `company.name`) during extraction so the wizard keeps running, logs the warning, and highlights the critical fields recruiters need to fill manually.
  DE: Schema-Validierungslücken (z. B. fehlendes `company.name`) während der Extraktion abgefangen, sodass der Wizard weiterläuft, die Warnung protokolliert und die kritischen Felder für die manuelle Nachpflege hervorhebt.

- EN: Gave the Work schedule dropdown its own spaced row in the Employment step so it no longer crowds neighbouring controls in light or dark mode.
  DE: Dem Dropdown für das Arbeitszeitmodell im Beschäftigungs-Schritt eine abgesetzte, luftige Zeile gegeben, damit es in hellem wie dunklem Modus nicht mehr mit anderen Feldern kollidiert.

- EN: Introduced consistent section headings, dividers, and expanders across the wizard (role tasks vs. skills, job-ad source excerpts) so every step is clearly separated and easier to scan.
  DE: Einheitliche Abschnittsüberschriften, Trenner und Aufklapper im Wizard ergänzt (Aufgaben vs. Skills, Stellenanzeigen-Auszüge), damit jede Stufe klar abgegrenzt und leichter erfassbar ist.

- EN: Updated the README with `.env` setup, Streamlit launch steps, and a walkthrough of the multi-step interface (Role Tasks, Summary tabs, Interview guide navigation).
  DE: README mit `.env`-Setup, Streamlit-Startschritten und einer Beschreibung des Multi-Step-Interfaces (Aufgaben, Summary-Tabs, Interviewleitfaden-Navigation) ergänzt.

- EN: Highlighted the strengthened skill-extraction pipeline in the README so job ads with mixed bullets still yield clean hard/soft/tool/language splits.
  DE: Die verstärkte Skill-Extraktion im README hervorgehoben, damit Stellenanzeigen mit gemischten Stichpunkten weiterhin saubere Hard-/Soft-/Tool-/Sprachaufteilungen liefern.

- EN: Added a bilingual "Help & guidance" sidebar expander that explains the Role Tasks analysis, Summary exports, and AI-powered interview guide requirements (internet/API key, fixed schema) so first-time users know what to expect.
  DE: Einen zweisprachigen Sidebar-Aufklapper „Hilfe & Hinweise“ ergänzt, der Aufgabenanalyse, Summary-Exporte und die KI-basierte Interviewleitfaden-Generierung (Internet/API-Key, behobenes Schema) erklärt, damit Erstnutzer:innen wissen, was sie erwartet.

- EN: Split the Summary export tools into dedicated tabs (Role tasks & search, Job ad, Interview guide) so recruiters navigate outputs without scrolling a single long page.
  DE: Export-Werkzeuge der Summary in eigene Tabs (Aufgaben & Suche, Stellenanzeige, Interviewleitfaden) aufgeteilt, damit Recruiter:innen die Ergebnisse ohne endloses Scrollen durchgehen können.

- EN: Added clear subheaders on the Summary step to separate the original job-ad excerpt from AI-generated suggestions so reviewers can scan sources versus model output at a glance.
  DE: Deutliche Zwischenüberschriften im Summary-Schritt ergänzt, um den Originalauszug der Stellenanzeige klar von den KI-Vorschlägen zu trennen und Quellen versus Modelloutput auf einen Blick erkennbar zu machen.

- EN: Centralised OpenAI response schemas in `llm/response_schemas.py`, validated them before dispatch, and added concise logging plus deterministic fallbacks when schemas are invalid or responses come back empty.
  DE: OpenAI-Response-Schemas in `llm/response_schemas.py` gebündelt, vor dem Versand validiert und bei ungültigen Schemas oder leeren Antworten klare Logs sowie einen deterministischen Fallback hinterlegt.

- EN: Queued interview-guide generation outside the UI layer and cached the results in `st.session_state`, so rerenders read existing data instead of repeating LLM calls.
  DE: Die Interviewleitfaden-Generierung aus der UI-Schicht ausgelagert und in `st.session_state` zwischengespeichert, damit Neu-Renderings auf vorhandene Daten zugreifen und keine LLM-Aufrufe doppelt ausführen.

- EN: Fixed the Role & Tasks skill board so skill chips render as styled badges instead of raw HTML strings.
  DE: Skill-Chips im Schritt „Aufgaben" werden wieder als gestaltete Badges statt als roher HTML-Text angezeigt.

- EN: Mapped benefit/perk sections such as "Wir bieten" or inline "Benefits, …" lists into compensation.benefits so perks from job ads are no longer dropped during extraction.
  DE: Benefit-/Perk-Abschnitte wie „Wir bieten“ oder Inline-Listen mit „Benefits, …“ werden nun in compensation.benefits übernommen, damit Vorteile aus Stellenanzeigen nicht mehr verloren gehen.

- EN: Removed unsupported `uniqueItems` flags from the pre-extraction analysis JSON schema (and all Responses schemas) so OpenAI accepts the payloads without schema errors.
  DE: Nicht unterstützte `uniqueItems`-Marker aus dem Pre-Extraction-Analyse-JSON-Schema (und allen Responses-Schemas) entfernt, damit OpenAI die Payloads ohne Schemafehler akzeptiert.

- EN: Expanded German-aware skill classification so soft skills (Teamfähigkeit/Kundenorientierung), languages (Englisch/Deutsch with levels), and programming languages or tools (Python, Jira, Excel) land in the correct requirements buckets instead of being lumped into hard skills.
  DE: Die deutsche Skill-Klassifizierung wurde erweitert, sodass Soft Skills (Teamfähigkeit/Kundenorientierung), Sprachen (Englisch/Deutsch mit Level) sowie Programmiersprachen oder Tools (Python, Jira, Excel) in den passenden Requirements-Buckets landen und nicht mehr bei den Hard Skills zusammenfallen.

- EN: Added inline "Tech Stack" heading recognition so tools, languages, and certifications listed on a single line are captured into requirements (e.g., Python/TensorFlow/AWS, English/German, PMP).
  DE: "Tech Stack"-Überschriften mit Inline-Listen werden jetzt erkannt, sodass Tools, Sprachen und Zertifizierungen auf einer Zeile korrekt in die Requirements übernommen werden (z. B. Python/TensorFlow/AWS, Englisch/Deutsch, PMP).

- EN: Hardened extraction fallbacks so empty or invalid Responses payloads return an empty profile and heuristic parsing rather than crashing the wizard.
  DE: Extraktions-Fallback robuster gemacht, sodass leere oder ungültige Responses-Payloads ein leeres Profil liefern und heuristisch fortfahren, statt den Wizard abzubrechen.

- EN: Refreshed the README with a top-level "Getting started" guide (install/run steps, env var table), architecture and model-routing overview, and a link to a new example input/output file so newcomers can launch the wizard quickly.
  DE: README mit einem prominenten „Getting started“-Abschnitt (Installations-/Startanleitung, Umgebungsvariablen-Tabelle), Architektur- und Modell-Routing-Überblick sowie Verweis auf eine neue Beispiel-Ein-/Ausgabe ergänzt, damit Neueinsteiger:innen den Wizard schneller nutzen können.

- EN: Added a bilingual "Hide intro"/"Intro ausblenden" toggle to the hero banner that remembers the session choice so users can reclaim form space after onboarding.
  DE: Zweisprachiger Schalter „Intro ausblenden“/"Hide intro" im Hero-Banner, der die Session-Auswahl speichert, damit Nutzer:innen nach dem Onboarding mehr Platz fürs Formular haben.

- EN: Improved task extraction reliability by recognising "Task List"/"Key Responsibilities" headings and instructing the extractor to keep every duty as its own bullet without merging.
  DE: Zuverlässigere Aufgabenerkennung durch Erkennen von Überschriften wie „Task List“/„Key Responsibilities“ und klare Vorgaben, jede Aufgabe als eigenen Stichpunkt unverändert zu übernehmen.

- EN: Introduced an “Extraction settings” expander on onboarding so recruiters can switch parsing mode (Fast vs. Thorough), choose the base model, and disable strict JSON schemas when ads fail validation.
  DE: Neuer Aufklapper „Extraktionseinstellungen“ im Onboarding, in dem Recruiter:innen den Parsing-Modus (Schnell vs. Gründlich) wählen, das Basismodell festlegen und bei Validierungsproblemen die strikten JSON-Schemas deaktivieren können.

- EN: Consolidated the strict-format extraction toggle to a single session key so the UI checkbox and backend parsing stay in sync across reruns.
  DE: Den Strict-Format-Schalter auf einen einzigen Sitzungsschlüssel vereinheitlicht, damit Checkbox und Backend-Parsen über Wiederholungen hinweg synchron bleiben.

- EN: Added a bilingual "Re-run extraction" control that clears the cached digest and triggers parsing again after users tweak parsing mode, model overrides, language, or strict formatting.
  DE: Neuer zweisprachiger Schalter „Extraktion erneut ausführen“, der den gecachten Digest leert und das Parsing erneut startet, sobald Nutzer:innen Parsing-Modus, Modell-Override, Sprache oder den Strict-Schalter anpassen.

- EN: Clarified the strict JSON toggle label and added a bilingual help tooltip so non-technical users know to disable strict formatting when extraction fails.
  DE: Beschriftung des Strict-JSON-Schalters präzisiert und einen zweisprachigen Hilfetext ergänzt, damit auch Nicht-Tech-Nutzer:innen wissen, dass sie die strikte Formatierung bei Extraktionsproblemen deaktivieren können.

- EN: Role & Tasks step now stacks responsibilities and requirements into full-width panels with taller text areas so long bullet lists stay readable on narrow screens without nested scrollbars.
  DE: Im Schritt „Aufgaben“ sind Verantwortlichkeiten und Anforderungen als untereinander liegende, breitflächige Panels mit höherer Texteingabe umgesetzt, damit lange Stichpunktlisten auf schmalen Ansichten ohne verschachtelte Scrollleisten lesbar bleiben.

- EN: Added a user-facing "Show parsing details" expander in the onboarding extraction review that reveals the raw NeedAnalysisProfile JSON so recruiters can inspect empty/null fields without needing the admin debug panel.
  DE: Im Onboarding-Review gibt es jetzt einen sichtbaren „Parsing-Details“-Expander, der das unveränderte NeedAnalysisProfile-JSON der KI zeigt, damit Recruiter:innen leere/null Felder prüfen können – ganz ohne Admin-Debug-Panel.

- EN: Strengthened the extraction prompt with a codex-style JSON schema example and explicit German section cues (Anforderungen vs. Aufgaben) so skills map reliably into the requirements fields.
  DE: Extraktions-Prompt um ein Codex-Style-JSON-Beispiel und klare deutsche Abschnitts-Hinweise (Anforderungen vs. Aufgaben) ergänzt, damit Skills zuverlässig in die Requirements-Felder einsortiert werden.

- EN: German heading detection now treats "Jobbeschreibung" and "Tätigkeitsbeschreibung" as responsibility cues and stops requirements capture when encountering benefits headers like "Wir bieten" or "Das bieten wir", preventing tasks and skills from merging.
  DE: Die Überschriften-Erkennung stuft „Jobbeschreibung“ und „Tätigkeitsbeschreibung“ jetzt als Aufgaben-Hinweise ein und beendet die Anforderungs-Erfassung bei Benefit-Headern wie „Wir bieten“ oder „Das bieten wir“, damit Aufgaben- und Skill-Listen getrennt bleiben.

- EN: Strengthened responsibility parsing so action-led bullets stay under `responsibilities.items` and their embedded skill/tool cues are split into the corresponding `requirements.*` lists, ensuring duties never leak into qualifications.
  DE: Die Aufgaben-Logik wurde geschärft: Aktionsbasierte Bullets bleiben in `responsibilities.items`, während eingebettete Skill-/Tool-Hinweise automatisch den passenden `requirements.*`-Listen zugeordnet werden – so wandern Aufgaben nicht mehr in die Anforderungen.

- EN: Introduced an explicit `APIMode` enum and per-call `api_mode` overrides for `call_chat_api` and `stream_chat_api` so OpenAI backend selection no longer depends on temporary global flags.
  DE: Neues `APIMode`-Enum und pro-Aufruf-Overrides über `api_mode` für `call_chat_api` und `stream_chat_api`, damit die Wahl zwischen Responses- und Chat-Backend nicht mehr von temporären globalen Flags abhängt.

- EN: Added an optional schema-function fallback that routes rejected Responses payloads through chat-completions function calling, keeping structured outputs aligned when strict schemas prove brittle.
  DE: Optionaler Schema-Fallback leitet abgewiesene Responses-Payloads über Function Calling der Chat-Completions-API, damit strukturierte Ergebnisse auch bei strengen Schemas stabil bleiben.

- EN: Documented refactor targets for the OpenAI client and ingestion heuristics so contributors can follow the planned splits before editing the large modules.
  DE: Refactoring-Ziele für den OpenAI-Client und die Ingestion-Heuristiken dokumentiert, damit Contributor:innen die geplanten Aufteilungen kennen, bevor sie die großen Module anpassen.
- EN: Centralised OpenAI retry/backoff handling in a shared decorator and split chat vs. Responses payload builders into dedicated classes for reuse and focused testing.
  DE: Zentrales Retry-/Backoff-Handling für OpenAI in einem gemeinsamen Decorator gebündelt und die Payload-Builder für Chat bzw. Responses in eigene Klassen aufgeteilt, um Wiederverwendung und gezielte Tests zu erleichtern.

- EN: Added a schema alignment guard that compares the NeedAnalysis model, the checked-in JSON schema, and the prompt field list while auto-injecting the canonical schema fields into the extractor prompt to prevent drift.
  DE: Neuer Schema-Abgleich testet NeedAnalysis-Modell, eingechecktes JSON-Schema und Prompt-Feldliste und injiziert die kanonischen Schema-Felder automatisch in den Extraktions-Prompt, um Abweichungen zu verhindern.

- EN: Structured extraction now issues a targeted retry when entire critical sections are missing (responsibilities, culture notes, or process overview), asking the AI for just those fields before defaulting to the empty profile.
  DE: Fehlen komplette Schlüsselsektionen (Aufgaben, Kulturhinweise oder Prozess-Overview), startet die Extraktion automatisch einen fokussierten Zweitversuch, der nur diese Felder nachfordert, bevor auf das leere Profil zurückgefallen wird.

- EN: Precise extraction now forces a high-effort model tier and injects rule-based section cues (e.g., Aufgaben/Anforderungen) into the prompt so responsibilities and requirements are captured more reliably.
  DE: Die präzise Extraktion nutzt jetzt ein Modell mit hoher Reasoning-Stufe und fügt regelbasierte Abschnittshinweise (z. B. Aufgaben/Anforderungen) in den Prompt ein, damit Aufgaben- und Anforderungsblöcke zuverlässiger erkannt werden.

- EN: Added a post-processing skill splitter that rebalances collapsed lists (hard vs. soft skills, languages, tools, certifications) and a few-shot prompt hint to keep categories separated when the extractor mixes them.
  DE: Neuer Nachbearbeitungs-Skill-Splitter verteilt zusammengefallene Listen (Hard/Soft Skills, Sprachen, Tools, Zertifizierungen) neu, und ein Few-Shot-Prompt-Hinweis hält die Kategorien getrennt, falls der Extraktor sie vermischt.

- EN: Clarified the extraction prompt to force duties vs. qualification bullets into the correct buckets so mixed lists no longer merge responsibilities with skills or languages.
  DE: Extraktions-Prompt präzisiert, damit gemischte Bullet-Listen zuverlässig in Aufgaben bzw. Anforderungen (Skills/Sprachen) aufgeteilt werden und nicht mehr zusammenfallen.

- EN: Added a reporting-line heuristic that captures "reports to …" phrases alongside explicit team-size and direct-report hints so team context fields prefill reliably.
  DE: Neue Heuristik fängt „reports to …“-Formulierungen sowie explizite Angaben zu Teamgröße und Direct Reports ab, damit die Teamkontextfelder zuverlässig vorbefüllt werden.

- EN: Improved recruiter contact extraction by recognising labelled HR lines (e.g., "Your contact" or "Ansprechpartner: Name") and pairing nearby emails/phones using tighter proximity checks.
  DE: Verbesserte Recruiter-Kontakt-Extraktion durch die Erkennung markierter HR-Zeilen (z. B. „Your contact“ oder „Ansprechpartner: Name“) und eine engere Zuordnung nahegelegener E-Mails/Telefonnummern.

- EN: Responses schema now marks `company.name` as required (empty or `null` values remain allowed) so OpenAI's strict schema validation no longer flags missing keys.
  DE: Das Responses-Schema kennzeichnet `company.name` jetzt als Pflichtfeld (leere oder `null`-Werte bleiben zulässig), sodass die strikte OpenAI-Schema-Validierung keine fehlenden Schlüssel mehr meldet.

- EN: Added an OpenAI request adapter that prunes unsupported fields, normalises Responses-to-chat fallbacks, and treats `invalid_json_schema` errors as non-retriable to avoid replaying malformed payloads.
  DE: Neuer OpenAI-Request-Adapter entfernt nicht unterstützte Felder, normalisiert Responses-zu-Chat-Fallbacks und behandelt `invalid_json_schema`-Fehler als nicht wiederholbar, damit fehlerhafte Payloads nicht erneut gesendet werden.

- EN: Requirements now include ESCO-aligned `skill_mappings` that normalize skill labels and attach URIs after extraction, so downstream matching can rely on standard taxonomy identifiers.
  DE: Die Requirements enthalten jetzt ESCO-ausgerichtete `skill_mappings`, die Skill-Bezeichnungen normalisieren und nach der Extraktion URIs hinzufügen, damit nachgelagerte Matching-Logik auf Standard-Taxonomie-IDs zugreifen kann.

- EN: Wizard steps now surface contextual intros, highlight AI-prefilled inputs with 🛈 badges, and warn on the Summary step when critical fields are still missing so exports stay complete.
  DE: Wizard-Schritte zeigen kontextuelle Intros, markieren KI-vorbefüllte Felder mit 🛈-Badges und warnen in der Summary vor fehlenden Pflichtfeldern, damit Exporte vollständig bleiben.

- EN: Inline follow-up questions now use info/warning accents, a tinted critical state, and hoverable “AI suggestion”/“KI-Vorschlag” labels on prefilled badges so accessibility cues stay consistent.
  DE: Inline-Follow-ups nutzen jetzt Info-/Warn-Akzente, einen getönten kritischen Zustand sowie Hover-Labels „AI suggestion“/„KI-Vorschlag“ auf vorbefüllten Badges, damit die Zugänglichkeit konsistent bleibt.

- EN: Structured extraction now retries Responses up to three times and, when plain-text fallbacks are unparsable, continues with an empty NeedAnalysisProfile so heuristics and follow-up generation stay available.
  DE: Die strukturierte Extraktion versucht Responses nun bis zu drei Mal und nutzt bei nicht parsebaren Plain-Text-Fallbacks ein leeres NeedAnalysisProfile, damit Heuristiken und Anschlussfragen weiter funktionieren.

- EN: Rule-based ingest now backfills generic emails/phones, location lines, and travel or team-size clues before invoking the LLM so contact, city, and workload fields rarely stay blank.
  DE: Die regelbasierte Ingestion ergänzt nun allgemeine E-Mail-/Telefonangaben, Standortzeilen sowie Reise- oder Teamgrößenhinweise vor dem LLM-Aufruf, damit Kontakt-, Stadt- und Arbeitslastfelder selten leer bleiben.

- EN: Structured extraction now separates hard skills, soft skills, languages, certifications, and tools into the NeedAnalysis requirements fields with a fallback classifier that splits combined skill lists automatically.
  DE: Die strukturierte Extraktion trennt jetzt Hard Skills, Soft Skills, Sprachen, Zertifizierungen und Tools in die NeedAnalysis-Anforderungsfelder und nutzt einen Fallback-Klassifizierer, der zusammengefasste Skill-Listen automatisch aufteilt.

- EN: Added regression tests for extraction repairs without `company.name`, schema-backed interview guide calls, and Streamlit session updates to prevent related crashes from resurfacing.
  DE: Regressionstests ergänzt, die Extraktionsreparaturen ohne `company.name`, schema-gestützte Interview-Guide-Aufrufe und Streamlit-Session-Updates abdecken, damit die behobenen Abstürze nicht zurückkehren.
- EN: Made `company.name` optional in the NeedAnalysis/Responses schema, routed missing names into inline follow-up cards instead of validation errors, and added coverage for the skill splitter that separates technical, soft, tool, and certification hints.
  DE: `company.name` im NeedAnalysis-/Responses-Schema optional gestellt, fehlende Namen wandern jetzt in Inline-Follow-ups statt zu Validierungsfehlern zu führen, und der Skill-Splitter für Technik-, Soft-, Tool- und Zertifizierungshinweise ist testseitig abgedeckt.

- EN: Documented that follow-up cards must keep using widget return values and `_update_profile(..., session_value=...)` instead of mutating canonical `st.session_state` keys after mount, so contributors avoid reintroducing immutable-session errors.
  DE: Dokumentiert, dass Follow-up-Karten weiterhin über Widget-Rückgabewerte und `_update_profile(..., session_value=...)` syncen müssen, statt kanonische `st.session_state`-Keys nach dem Mount zu verändern, damit keine Fehler zu unveränderlichen Sessions zurückkehren.

- EN: The wizard no longer blocks the Next button when required fields are empty; a bilingual hint now appears instead so recruiters can continue and fill gaps later.
  DE: Der Wizard blockiert den „Weiter“-Button bei fehlenden Pflichtfeldern nicht mehr; stattdessen erscheint ein zweisprachiger Hinweis, damit Recruiter:innen weitergehen und Lücken später schließen können.

- EN: Added early schema repair after extraction so missing critical sections (e.g., `company.name`) are default-filled and reported to the wizard banner before any UI renders, avoiding downstream crashes from absent keys.
  DE: Frühzeitige Schema-Reparatur nach der Extraktion hinzugefügt, damit fehlende kritische Abschnitte (z. B. `company.name`) mit Standardwerten ergänzt und vor dem Rendern des UIs in der Wizard-Warnleiste gemeldet werden – so lassen sich Abstürze durch fehlende Schlüssel vermeiden.
- EN: Expanded the RecruitingWizard alias coverage (department/team fallbacks, HQ and branding keys, city fallbacks) and pruned unknown fields before validation so legacy JSON from earlier releases keeps validating without extra manual cleanup.
  DE: Die RecruitingWizard-Alias-Abdeckung wurde erweitert (Fallbacks für Abteilung/Team, HQ- und Branding-Schlüssel, Städte-Fallbacks) und unbekannte Felder werden vor der Validierung entfernt, damit Legacy-JSON aus früheren Versionen ohne zusätzlichen manuellen Aufwand gültig bleibt.
- EN: Localized compensation selectors now display currency and pay-period choices in the active language while keeping canonical values, and the free-text currency path uses bilingual copy so the "Other" branch stays consistent across DE/EN.
  DE: Die Vergütungsfelder zeigen Währungs- und Periodenauswahl jetzt in der aktiven Sprache bei unveränderten Kanonwerten an; der Freitextpfad für "Andere" nutzt zweisprachige Hinweise, sodass der Zweig in DE/EN konsistent bleibt.
- EN: When validation inserts placeholder defaults or drops invalid fields, the wizard now surfaces a bilingual banner (EN/DE) in every step after loading the profile, listing the impacted schema paths recruiters should revisit.
  DE: Sobald die Validierung Platzhalter ergänzt oder ungültige Felder entfernt, blendet der Wizard nach dem Laden des Profils in allen Schritten ein zweisprachiges Banner ein und listet die betroffenen Schema-Pfade auf, die Recruiter:innen prüfen sollten.
- EN: Hardened OpenAI retry/fallbacks: invalid JSON schema errors now short-circuit retries, and Responses → Chat fallbacks reuse the same schema-format builder so both APIs receive the `name` + `schema` pair consistently.
  DE: OpenAI-Retries/-Fallbacks robuster gemacht: Ungültige JSON-Schema-Fehler brechen Wiederholungen sofort ab, und Responses-→-Chat-Fallbacks nutzen denselben Schema-Builder, damit beide APIs immer das Paar aus `name` und `schema` erhalten.

- EN: Refactored the monolithic `wizard/flow.py` into focused helpers (`wizard/sections/followups.py`, `wizard/date_utils.py`, `wizard/state_sync.py`, `wizard/types.py`) so follow-up rendering, date utilities, and widget state syncing are easier to maintain and unit test.
  DE: Die monolithische `wizard/flow.py` wurde in fokussierte Helfer zerlegt (`wizard/sections/followups.py`, `wizard/date_utils.py`, `wizard/state_sync.py`, `wizard/types.py`), damit Follow-up-Rendering, Datumshelfer und Widget-State-Sync leichter wartbar und testbar sind.

- EN: Expanded `docs/DEV_GUIDE.md` with bilingual guidance that covers `wizard/sections/followups.py`, `CRITICAL_FIELD_PROMPTS`, and the `PAGE_FOLLOWUP_PREFIXES` / `FIELD_SECTION_MAP` metadata so contributors know how to register new critical follow-ups without desynchronising schema gating.
  DE: `docs/DEV_GUIDE.md` enthält jetzt zweisprachige Hinweise zu `wizard/sections/followups.py`, `CRITICAL_FIELD_PROMPTS` sowie den Metadaten `PAGE_FOLLOWUP_PREFIXES` / `FIELD_SECTION_MAP`, damit Contributor:innen neue kritische Follow-ups hinzufügen können, ohne die Schema- und Navigationslogik aus dem Takt zu bringen.

- EN: Enforced critical structured-output sections: the NeedAnalysis parser now errors when responsibilities, company culture, or hiring-process notes are blank, and the structured Job Ad generator rejects payloads with empty overview/responsibility/requirement/how-to-apply/equal-opportunity sections or missing target audiences so HR deliverables stay complete.
  DE: Kritische Abschnitte für strukturierte Ausgaben werden jetzt erzwungen: Der NeedAnalysis-Parser schlägt fehl, sobald Verantwortlichkeiten, Unternehmenskultur oder Prozesshinweise leer sind, und der strukturierte Stellenanzeigen-Generator weist Payloads mit leerem Überblick, Aufgaben-, Anforderungs-, Bewerbungs- oder Equal-Opportunity-Abschnitt bzw. fehlender Zielgruppe zurück, damit HR-Artefakte vollständig bleiben.

- EN: Tightened the job-ad, interview-guide, and follow-up question prompts so every section explicitly mirrors the structured vacancy data, uses inclusive/bias-free HR language, references the relevant schema fields (job title, seniority, work policy, etc.), and only asks for job-relevant clarifications with realistic answer suggestions.
  DE: Die Prompts für Stellenanzeigen, Interviewleitfäden und Nachfragen wurden geschärft: Alle Abschnitte spiegeln jetzt die strukturierten Vakanzdaten exakt wider, nutzen inklusive HR-Terminologie, verweisen auf die passenden Schemafelder (Jobtitel, Seniorität, Arbeitsmodell etc.) und stellen nur noch jobrelevante, realistische Rückfragen samt Antwortoptionen.

- EN: Strengthened the interview guide generator prompt so competency clusters stem from the vacancy profile, each competency powers at least one question, every list explicitly mixes technical/behavioural/cultural prompts (flagged via questions[].type), and each entry includes two evaluation criteria for consistent scoring.
  DE: Den Interview-Guide-Prompt erweitert, damit die Kompetenzcluster aus dem Vakanzprofil abgeleitet werden, jede Kompetenz mindestens eine Frage erhält, jede Liste explizit technische, verhaltensorientierte und kulturelle Fragen (gekennzeichnet über questions[].type) enthält und pro Frage zwei Bewertungskriterien für eine konsistente Beurteilung aufgeführt sind.

- EN: Moved every debug/API toggle plus the salary/ESCO JSON diagnostics into the admin-only expander; recruiters never see these controls or raw payloads unless `ADMIN_DEBUG_PANEL=1` and the debug mode is enabled inside that panel.
  DE: Alle Debug-/API-Schalter sowie die Gehalts- bzw. ESCO-Rohdaten wurden in den Admin-Expander verschoben – Recruiter:innen sehen sie nur, wenn `ADMIN_DEBUG_PANEL=1` gesetzt ist und der Debugmodus innerhalb dieses Panels aktiviert wurde.

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
- EN: Added regression tests to validate InterviewGuide model dumps against the shared schema, to verify alias canonicalisation survives normalize_profile(), and to detect drift between `schema/need_analysis.schema.json` and the generated Responses schema; run `python scripts/propagate_schema.py --apply` whenever the sync test fails.
  DE: Regressionstests ergänzt, die Interview-Guide-Modelldumps gegen das gemeinsame Schema prüfen, sicherstellen, dass Alias-Kanonisierung normalize_profile() übersteht, und Abweichungen zwischen `schema/need_analysis.schema.json` und dem generierten Responses-Schema melden; bei einem fehlgeschlagenen Sync-Test `python scripts/propagate_schema.py --apply` ausführen.
- EN: Locked down every Responses JSON schema: the pipeline tests now assert `additionalProperties: false` across all nested objects and the structured Job Ad schema requires the metadata block (tone plus target audience), preventing stray keys and missing context in model outputs.
  DE: Sämtliche Responses-JSON-Schemas wurden verschärft – die Pipeline-Tests prüfen nun `additionalProperties: false` in allen verschachtelten Objekten und das strukturierte Job-Ad-Schema verlangt den Metadatenblock (Ton und Zielgruppe), sodass keine unerwarteten Felder mehr auftauchen und keine Pflichtkontexte fehlen.
- EN: Added regression tests that validate InterviewGuide JSON responses against the schema and ensure NeedAnalysis department/team aliases survive canonicalization, preventing future schema propagation regressions.
  DE: Regressionstests ergänzt, die InterviewGuide-JSON-Antworten gegen das Schema prüfen und sicherstellen, dass NeedAnalysis-Aliasfelder für Abteilung/Team die Kanonisierung überstehen, damit künftige Schema-Propagationsregressionen ausbleiben.

Fixed / Behoben

- EN: The Interview Guide schema now forces `focus_areas.label` into the `required` list inside `$defs`, preventing the Responses API from rejecting the JSON schema with a "Missing 'label'" error and keeping AI-generated guides available in the wizard.
  DE: Das Interviewleitfaden-Schema zwingt `focus_areas.label` jetzt in die `required`-Liste innerhalb von `$defs`, sodass die Responses-API das JSON-Schema nicht mehr mit einem „Missing 'label'“-Fehler ablehnt und KI-Generierungen im Wizard erhalten bleiben.

- EN: Applied `_ensure_required_fields` recursively in the NeedAnalysis schema builder so every nested object (including `company.name`) appears in `required` arrays and Responses no longer rejects missing keys.
  DE: `_ensure_required_fields` im NeedAnalysis-Schema-Builder jetzt rekursiv angewendet, sodass jedes verschachtelte Objekt (inkl. `company.name`) in den `required`-Listen steht und Responses keine Missing-Key-Fehler mehr meldet.

- EN: Chat fallbacks now drop the `strict` flag from JSON schemas before hitting the classic Chat Completions API, preventing "Unknown parameter: 'response_format.strict'" errors when Responses falls back.
  DE: Chat-Fallbacks entfernen das `strict`-Flag nun aus JSON-Schemas, bevor die klassische Chat-Completions-API aufgerufen wird, sodass keine Fehler „Unknown parameter: 'response_format.strict'“ mehr auftreten, wenn Responses zurückfällt.

- EN: Company contact emails entered via the wizard are now validated with the same Pydantic `EmailStr` parser as the schema, so malformed addresses raise the bilingual inline error message instead of throwing a Python `TypeError` and interrupting the form.
  DE: Im Wizard eingegebene Kontakt-E-Mails werden jetzt über den gleichen Pydantic-`EmailStr`-Parser geprüft wie im Schema, sodass fehlerhafte Adressen den zweisprachigen Inline-Hinweis anzeigen, anstatt einen Python-`TypeError` zu verursachen und das Formular zu unterbrechen.
- EN: Resetting or restarting the wizard now removes every stored follow-up question plus their `fu_*` focus sentinels so the sidebar and inline cards never resurface stale prompts after a restart.
  DE: Beim Zurücksetzen oder Neustarten des Wizards werden sämtliche gespeicherten Follow-up-Fragen sowie die zugehörigen `fu_*`-Fokus-Sentinels entfernt, sodass weder Sidebar noch Inline-Karten veraltete Prompts nach einem Neustart erneut anzeigen.
- EN: Follow-up cards in the Onboarding extraction review now render directly beneath their fields (company/contact, reporting line, responsibilities, timing) via the shared `wizard-followup-item` layout, keep the red required prefix in all locales, and emit the critical-warning toast only once per question.
  DE: Die Follow-up-Karten der Onboarding-Extraktionsübersicht erscheinen jetzt unmittelbar unter ihren Feldern (Unternehmen/Kontakt, Berichtslinie, Aufgaben, Timing) über das gemeinsame `wizard-followup-item`-Layout, behalten in allen Sprachen den roten Pflicht-Prefix und zeigen die Warn-Toast je kritischer Frage nur ein einziges Mal.


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
- EN: Streaming completions now detect missing `response.completed` events *and* empty final payloads, replay the request without streaming, and only then fall back to Chat Completions when needed, preventing partial outputs and noisy tracebacks in Streamlit logs.
  DE: Streaming-Antworten erkennen fehlende `response.completed`-Events sowie leere Final-Payloads, spielen die Anfrage ohne Streaming erneut ab und greifen nur bei Bedarf auf Chat-Completions zurück – so verschwinden Teilantworten und laute Tracebacks aus den Streamlit-Logs.
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

chore: consolidate company logo session key and expand title aliases for schema payloads

Wartung: Sitzungsschlüssel für Firmenlogos vereinheitlicht und Titel-Aliasse im Schema erweitert

fix: map "Must Have"/"Nice To Have" skill sections into required vs. optional requirements, keep German "Anforderungen" bullets in requirements, and route tools into tools_and_technologies instead of mixing all skills together

Fix: "Must Have"-/"Nice To Have"-Skill-Abschnitte werden den Pflicht- bzw. Optional-Requirements zugeordnet, deutsche "Anforderungen"-Stichpunkte bleiben in den Requirements, und Tools wandern in tools_and_technologies statt alle Skills zu vermischen

fix: align NeedAnalysisProfile JSON schema required flags with the Pydantic model and regenerate the Responses schema artifact

Fix: NeedAnalysisProfile-JSON-Schema-Required-Flags an das Pydantic-Modell angepasst und das Responses-Schema-Artefakt neu erzeugt

feat: parse reporting lines and direct report counts to prefill position.reports_to and position.supervises

Feature: Berichtslinien und Teamgrößen werden erkannt, um position.reports_to und position.supervises vorab zu befüllen
