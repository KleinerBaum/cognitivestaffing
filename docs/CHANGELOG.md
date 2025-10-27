# Changelog

## Unreleased

### Added / Neu
- **EN:** Automatic normalisation pipeline harmonises scraped fields (addresses noisy cities, boolean flags, currency formats).
  **DE:** Automatisierte Normalisierung harmonisiert extrahierte Felder (bereinigt Städte, Boolesche Werte, Währungsformate).
- **EN:** Company branding integration fetches logo, dominant colour, and claim for the wizard sidebar, exports, and JSON.
  **DE:** Unternehmensbranding integriert Logo, Leitfarbe und Claim in Sidebar, Exporte und JSON.
- **EN:** Codex prompting guide entries captured in this changelog to align internal task history.
  **DE:** Codex-Prompting-Guide-Einträge im Changelog ergänzt, um interne Aufgabenhistorie abzubilden.
- **EN:** Unified wizard widget factories (`components.widget_factory`) to bind schema
  paths with automatic `_update_profile` callbacks across all steps.
  **DE:** Vereinheitlichte Wizard-Widget-Fabriken (`components.widget_factory`), die
  Schema-Pfade mit automatischen `_update_profile`-Callbacks in allen Schritten koppeln.

### Fixed / Behoben
- **EN:** Centralised wizard profile key constants and session defaults so schema paths map through a single registry (CS_SCHEMA_PROPAGATE).
  **DE:** Profil-Schlüssel und Session-Defaults des Wizards zentralisiert, sodass Schema-Pfade über einen einzigen Katalog laufen (CS_SCHEMA_PROPAGATE).
- **EN:** Canonical NeedAnalysisProfile key registry now drives aliases and state/export sanitisation so legacy keys disappear after ingestion (CS_SCHEMA_PROPAGATE).
  **DE:** Der kanonische NeedAnalysisProfile-Key-Index steuert Alias- und State/Export-Bereinigung, sodass nach dem Import keine Legacy-Keys mehr verbleiben (CS_SCHEMA_PROPAGATE).
- **EN:** City normalization now strips leading prepositions, removes trailing fragments, and falls back to a structured LLM
  extraction when regex cleanup fails to find a result.
  **DE:** Die Städtereinigung entfernt führende Präpositionen, kappt kleingeschriebene Fragmente und nutzt bei leerem Regex-Ergebnis
  einen strukturierten LLM-Fallback.
- **EN:** Resolved synchronization gaps so extracted data reliably populates wizard forms after repair.
  **DE:** Synchronisationslücken geschlossen, damit extrahierte Daten nach Reparaturen zuverlässig in den Formularen landen.
- **EN:** Hardened OpenAI API key loading (Streamlit secrets → environment) and gated LLM-powered features when no key is present
  to prevent runtime warnings. **DE:** Laden des OpenAI-Schlüssels robuster gestaltet (Streamlit-Secrets → Umgebung) und LLM-
  Funktionen ohne Schlüssel sauber deaktiviert, damit zur Laufzeit keine Warnungen mehr erscheinen.

### Docs / Doku
- **EN:** Extended README, developer notes, and screenshots for normalisation, JSON repair, and branding caches.
  **DE:** README, Entwicklerhinweise und Screenshots zu Normalisierung, JSON-Reparatur und Branding-Caches erweitert.
- **EN:** Documented `.env.example`, the new LLM fallback behaviour, and setup notes for local development.
  **DE:** `.env.example`, das neue LLM-Fallback-Verhalten und Setup-Hinweise für die lokale Entwicklung dokumentiert.
- **EN:** Updated README with guidance on the widget factory pattern.
  **DE:** README mit Hinweisen zum Widget-Factory-Pattern aktualisiert.

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
