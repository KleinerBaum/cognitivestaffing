# Cognitive Staffing

Cognitive Staffing ist ein zweisprachiger (DE/EN) Streamlit-Wizard zur strukturierten Anforderungsanalyse für Recruiting. Die App verarbeitet Stelleninformationen (Text, URL, PDF, DOCX), überführt sie in ein `NeedAnalysisProfile` und erzeugt daraus recruiter-taugliche Artefakte (z. B. Job Ad Draft, Interview Guide, Boolean Search, JSON/Markdown-Export).

> Diese README ist für technische Reviewer ausgelegt und beschreibt Architektur, Betriebsmodell und Qualitätsprozesse ohne sicherheitskritische Interna offenzulegen.

## Kernfunktionen

- **8-stufiger Wizard** mit linearer Navigation (Back/Next) und Pflichtfeld-Gating.
- **Schema-zentrierte Datenhaltung** über JSON Schema + Pydantic-Modelle.
- **LLM-unterstützte Extraktion und Follow-ups** mit strukturierten Outputs.
- **Bilinguale UX** (DE/EN) für UI-Texte, Validierung und generierte Inhalte.
- **Export-Pipeline** für JSON/Markdown-Artefakte inkl. konsistenter Feldabbildung.

## Architektur (High-Level)

- **UI/Flow:** `app.py`, `wizard/`, `wizard_router.py`, `wizard/navigation/`
- **Datenvertrag:** `schema/need_analysis.schema.json`, `schema/need_analysis_envelope.schema.json`, `schemas.py`, `models/`
- **LLM/Runtime:** `openai_utils/`, `llm/`, `pipelines/`, `prompts/`
- **Follow-ups & Missing Fields:** `questions/`, `question_logic.py`, `wizard/services/followups.py`
- **Planning Context:** `wizard/planner/plan_context.py` provides a typed context envelope (role family, location, work policy, compliance, urgency, risk signals) shared by follow-up and decision prioritization.
- **Risk Detection (decision-first):** `wizard/planner/risk_detection.py` adds conservative, heuristic risk decision cards (e.g., stakeholder complexity, communication constraints, pressure patterns) in inferred mode so follow-up planning can prioritize collaboration/work-environment clarification without mutating profile facts.
- **Role-Overlay Registry:** `questions/overlays/role_questions.json` + `questions/overlays/role_registry.py` für kanonische ESCO-/Role-Family-Schlüssel inkl. Alias-Normalisierung und Fallback-Dokumentation.
- **Outputs/Exports:** `generators/`, `exports/`, `artifacts/`

### Prozessfluss

1. Ingestion im **Willkommen-/Landing-Step** (Datei/URL/Freitext)
2. Strukturierte Extraktion in `NeedAnalysisProfile` (automatisch nach URL/Upload bzw. via Freitext-Analyse)
   - Intake-Mapping ist zentral in `wizard/flow.py` verankert (`position.job_title`, `company.name`, `location.*`, `responsibilities.items`, `requirements.*`, `compensation.benefits`) inklusive robuster Listen-Normalisierung (Trim/Dedup/Empty-Filter).
3. Shadow-Envelope im Wizard-State (`profile_envelope_data`) für typed Facts/Inferences/Gaps/Plan/Risks/Evidence-Parallelführung inkl. Snapshot-Triggern (z. B. Extraktion, Step-Save)
4. Lückenanalyse je Wizard-Step
5. Follow-up-Fragen und manuelle Ergänzung
6. Validierung kritischer Felder
7. Generierung und Export der Artefakte


## Canonical Field Paths (ProfilePaths)

Bei neuen oder geänderten Profilfeldern gilt ein **canonical path**-Workflow:

1. Neues Feld als `ProfilePaths`-Konstante in `constants/keys.py` anlegen.
2. Python-Code (z. B. Follow-up-Logik) auf `ProfilePaths.*` referenzieren statt freie String-Literale zu nutzen.
3. JSON-Konfigurationen (`role_field_map.json`, `critical_fields.json`) dürfen String-Pfade enthalten, werden aber per Contract-Test gegen `ProfilePaths` abgesichert.
4. Relevante Schema/Model/UI/Export-Stellen gemäß Datenvertrag mitziehen und Tests aktualisieren.

**Migrationshinweis (Legacy Intake/Follow-ups):**
- `position.context` wird bei Intake-Mapping/Folgefragen auf `position.role_summary` normalisiert.
- `position.location` wird auf `location.primary_city` normalisiert.
- Legacy-Felder bleiben nur als Input-Aliases erlaubt; in Wizard/Export/Follow-up-Contracts werden ausschließlich kanonische Keys verwendet.

So bleibt `ProfilePaths` die Single Source of Truth für erlaubte Feldpfade in der Anwendung.

## LLM- und Responses-Policy

- Primäre Integration über **OpenAI Responses API**.
- **Strukturierte Ausgaben** müssen schema-konform angefordert und verarbeitet werden.
- Tool-basierte Flows nur mit expliziter Freigabe/Guardrails.
- Timeouts/Retry-Verhalten sind konfiguriert und dürfen nicht stillschweigend umgangen werden.

> Hinweis: Modellrouting und Reasoning-Einstellungen werden zentral per Konfiguration/Environment gesteuert. Keine hardcodierten Modellwechsel in Feature-Code einführen.

## Sicherheit & Datenschutz (öffentlich dokumentiert)

- Secrets/Keys niemals im Code oder in Logs hinterlegen.
- Konfiguration über Environment bzw. Secret-Management.
- Sensible Nutzdaten (z. B. Job-Ad-Inhalte) nur minimal und zweckgebunden verarbeiten.
- Debug-Ausgaben grundsätzlich ohne PII/Secret-Leaks.

## Setup (lokal)

```bash
python -m venv .venv
source .venv/bin/activate
poetry install --with dev
poetry run streamlit run app.py
```

## Konfiguration (Beispiel, gekürzt)

```env
OPENAI_API_KEY=<set-via-env-or-secret-store>
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_REQUEST_TIMEOUT=120

# optional
VECTOR_STORE_ID=<optional>
REASONING_EFFORT=minimal
```

> Keine produktiven Secrets in `.env.example`, Commits oder Tickets hinterlegen.

## Qualitäts-Gates (CI-blocking)

```bash
ruff format .
ruff check .
mypy --config-file pyproject.toml
pytest -q -m "not integration"
```

Alle Checks müssen vor dem Merge grün sein.

## Branching & Release-Prozess

- Feature-Branches: `feat/<kurz-beschreibung>`
- Pull Requests: gegen `dev`
- Merge nach `main`: via Merge-Train
- Jede PR enthält Release-Notes (user-facing + technische Änderungen)

## i18n- und Doku-Regeln

- Neue UI-Texte immer DE/EN konsistent pflegen.
- Bei funktionalen Änderungen README + Changelog aktualisieren.
- Bei sichtbaren UI-Änderungen zugehörige Screenshots in `images/` aktualisieren.

## Verwandte Dokumente

- `AGENTS.md` – Agent-/Contributor-Leitlinien
- `docs/CHANGELOG.md` – laufende Änderungen und Release-Historie
- `CONTRIBUTING.md` – Zusammenarbeit und Standards
