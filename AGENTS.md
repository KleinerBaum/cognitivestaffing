# AGENTS.md — Cognitive Staffing

Agent-Leitfaden für dieses Repository. Ergänzt `README.md` und gilt für alle Coding-Agents.

> Priorität: User-Instruktionen > nächstes `AGENTS.md` > übrige Repo-Dokumente.

---

## 1) Projektkontext

Cognitive Staffing ist ein bilingualer (DE/EN) Streamlit-Wizard zur Recruiting-Bedarfsanalyse.

Kernablauf:
1. Ingestion (PDF/DOCX/URL/Text)
2. Strukturierte Extraktion (`NeedAnalysisProfile`)
3. 8-Step-Wizard mit Pflichtfeld-Gating
4. Follow-ups zur Lückenschließung
5. Generierung + Export (u. a. Job Ad, Interview Guide, Boolean Search)

---

## 2) Nicht verhandelbare Produkt-Invarianten

### 2.1 Wizard-Vertrag

Fixe Schrittfolge:
1. Onboarding / Job Ad
2. Company
3. Team & Structure
4. Role & Tasks
5. Skills & Requirements
6. Compensation / Benefits
7. Hiring Process
8. Summary

Regeln:
- linearer Flow (Back/Next)
- `Next` nur aktiv bei erfüllten Pflichtfeldern
- keine implizite Reorder-/Skip-Logik

### 2.2 Step-Layout

Jeder Step folgt dem Muster:
1. **Known**
2. **Missing**
3. **Validate**
4. **Nav**

Assistenten/Tools nur in separaten Bereichen (z. B. Expander), nicht zwischen Pflichtfeldern.

### 2.3 Datenvertrag (Schema ↔ Modell ↔ UI ↔ Export)

Bei Feldänderungen immer konsistent propagieren:
- `schema/need_analysis.schema.json`
- `schemas.py`, `models/`
- `wizard/`, `wizard_pages/`, `ui_views/`
- `question_logic.py`, `questions/`, `wizard/services/followups.py`
- `wizard/metadata.py`, `critical_fields.json`
- `generators/`, `exports/`

Keine „dangling keys“ hinterlassen.

---

## 3) LLM-/Responses-Richtlinien

- Responses API bevorzugen.
- Strukturierte Outputs mit validierbarer Zielstruktur verwenden.
- Timeouts/Retries explizit halten (kein stilles Endpoint-/Modell-Driften).
- Konfiguration zentral steuern; keine Modell-Hardcodes in Feature-Logik.
- Tooling nur mit Guardrails; unsupported Tooltypen frühzeitig blockieren.

Wenn `VECTOR_STORE_ID` gesetzt ist, Retrieval über Vector Store aktivieren; sonst ohne Retrieval arbeiten.

---

## 4) Sicherheit & Datenschutz

- Keine API-Keys/Secrets im Code, in Tests oder Logs.
- `OPENAI_API_KEY` nur aus Environment/Secret-Store beziehen.
- PII/sensible Jobdaten in Logs minimieren oder redigieren.
- Öffentliche Doku nur auf High-Level (keine internen Sicherheitsdetails, keine Betriebsgeheimnisse).

---

## 5) Arbeitsregeln für Agents

### 5.1 Änderungsdisziplin

- Kleine, reviewbare Commits.
- Keine Misch-Refactors ohne funktionalen Bezug.
- Schnittstellen nur ändern, wenn alle Aufrufer angepasst werden.

### 5.2 Python-Standards

- Python ≥ 3.11
- PEP 8
- Typing-Hints verwenden

### 5.3 Branching / PR

- Branches: `feat/<kurz-beschreibung>`
- PR-Ziel: `dev`
- Merge nach `main` via Merge-Train
- PRs müssen Release-Notes enthalten

### 5.4 i18n & UI

- Neue UI-Texte immer DE/EN konsistent.
- Bei sichtbaren UI-Änderungen Screenshots in `images/` aktualisieren.

---

## 6) Verifikation

Vor Übergabe mindestens relevante Checks ausführen:

```bash
ruff format .
ruff check .
mypy --config-file pyproject.toml
pytest -q -m "not integration"
```

Zusätzlich bei Wizard-bezogenen Änderungen manuell prüfen:
- Wizard-Flow
- Summary
- JSON/Markdown-Export
- Boolean-String-Generator

Wenn ein Check in der Umgebung nicht ausführbar ist: transparent dokumentieren.

---

## 7) Definition of Done

Eine Änderung ist abgeschlossen, wenn:
- Feature im Wizard funktioniert,
- Step-Vertrag erhalten bleibt,
- Schema/Logik/UI/Export konsistent sind,
- DE/EN konsistent ist,
- relevante Checks/Verifikation dokumentiert sind,
- keine sensiblen Informationen in Doku/Logs offengelegt werden.
