## Schema (v2.1) / Schema (v2.1)

**EN:** The hierarchical schema groups related fields into categories such as `company`, `position`, and `compensation`. Priority levels (1–3) focus the extraction flow on mandatory information first. Example categories:
- **company:** `name`, `industry`, `hq_location`, `size`, `website`
- **position:** `job_title`, `seniority_level`, `department`, `management_scope`, `reporting_line`, `role_summary`, `team_structure`
- **employment:** `job_type`, `work_policy` (Onsite/Hybrid/Remote), `travel_required`, `work_schedule`
- **compensation:** `salary_currency`, `salary_min`, `salary_max`, `salary_period`, `benefits`
- **requirements:** `hard_skills`, `soft_skills`, `tools_and_technologies`, `education_level`, `languages_required`, `certificates`
- **responsibilities:** `items` (list of key responsibilities), `top3` (three highlights)

**DE:** Das hierarchische Schema gruppiert verwandte Felder in Kategorien wie `company`, `position` und `compensation`. Prioritäten (1–3) lenken die Extraktion zuerst auf Pflichtangaben. Beispielkategorien:
- **company:** `name`, `industry`, `hq_location`, `size`, `website`
- **position:** `job_title`, `seniority_level`, `department`, `management_scope`, `reporting_line`, `role_summary`, `team_structure`
- **employment:** `job_type`, `work_policy` (Onsite/Hybrid/Remote), `travel_required`, `work_schedule`
- **compensation:** `salary_currency`, `salary_min`, `salary_max`, `salary_period`, `benefits`
- **requirements:** `hard_skills`, `soft_skills`, `tools_and_technologies`, `education_level`, `languages_required`, `certificates`
- **responsibilities:** `items` (Liste der wichtigsten Aufgaben), `top3` (drei Highlights)

*EN/DE:* Weitere Bereiche (z. B. Kontakte, Prozess oder Analytics) existieren im Schema, kommen aber nicht in jeder Extraktion zum Einsatz. Alle Felder erscheinen im JSON – leere Strings für Text, leere Listen für Arrays. Die aktuelle `schema_version` lautet `"v2.1"`.

### Example output / Beispielausgabe

```json
{
  "schema_version": "v2.1",
  "company": {
    "name": "TechCorp",
    "industry": "Information Technology",
    "hq_location": "Berlin",
    "size": "201-1000",
    "website": "https://techcorp.example.com"
  },
  "position": {
    "job_title": "Senior Software Engineer",
    "seniority_level": "Senior",
    "department": "Engineering",
    "management_scope": "Individual Contributor",
    "reporting_line": "CTO",
    "role_summary": "Develop and maintain core platform features...",
    "team_structure": ""
  },
  "employment": {
    "job_type": "Full-time",
    "work_policy": "Hybrid",
    "travel_required": "False",
    "work_schedule": "Mon–Fri 9–5",
    "...": "..."
  },
  "compensation": {
    "salary_currency": "EUR",
    "salary_min": "60000",
    "salary_max": "80000",
    "salary_period": "year",
    "salary_provided": "True",
    "benefits": ["Health insurance", "Paid time off", "Learning budget"],
    "...": "..."
  },
  "requirements": {
    "hard_skills": ["Java", "Spring", "Microservices"],
    "soft_skills": ["Leadership", "Communication"],
    "tools_and_technologies": ["Docker", "Kubernetes"],
    "education_level": "Bachelor",
    "languages_required": ["English"],
    "certificates": [],
    "certifications": [],
    "...": "..."
  },
  "responsibilities": {
    "items": ["Design system architecture", "Lead code reviews", "Mentor junior developers"],
    "top3": []
  }
}
```

### Confidence metadata and locks / Confidence-Metadaten und Sperren

**EN:**
- `field_confidence` maps dot-paths to metadata entries. Each entry includes a `tier` (`rule_strong` for deterministic rule hits, `ai_assisted` for LLM output) and a `source` (`"rule"` or `"llm"`). Rule hits also log a pattern identifier and numeric `score`. The wizard renders icons (🔎 for rules, 🤖 for AI) and tooltips based on this data.
- `high_confidence_fields` lists authoritative fields that start locked. Rule passes populate the list; downstream heuristics add further entries (e.g. benefit bundles).
- `locked_fields` records fields that require an explicit unlock toggle before editing. Overlap with `high_confidence_fields` indicates strong rule confidence.

**DE:**
- `field_confidence` ordnet Dot-Pfade Metadaten zu. Jeder Eintrag enthält ein `tier` (`rule_strong` für Regel-Treffer, `ai_assisted` für KI-Output) sowie ein `source` (`"rule"` oder `"llm"`). Regel-Treffer speichern zusätzlich eine Pattern-ID und den numerischen `score`. Der Wizard zeigt darauf basierende Icons (🔎 für Regeln, 🤖 für KI) samt Tooltip an.
- `high_confidence_fields` führt Felder mit hoher Verlässlichkeit, die initial gesperrt bleiben. Regelprüfungen füllen die Liste, Heuristiken ergänzen weitere Felder (z. B. Benefits).
- `locked_fields` enthält Felder, die vor Änderungen aktiv entsperrt werden müssen. Überschneidungen mit `high_confidence_fields` deuten auf hohe Regel-Sicherheit hin.

*EN/DE:* Alle drei Strukturen liegen in `profile_metadata`, überleben erneute Extraktionsläufe und stellen sicher, dass bestehende Sperren und Hinweise respektiert werden.

## Normalisation & Key Alignment / Normalisierung & Key-Ausrichtung

**EN:** Every ingestion route must pass raw dictionaries through `coerce_and_fill`
before storing them in `st.session_state["profile"]`. The helper applies the
`ALIASES` mapping (e.g. `company.logo` → `company.logo_url`), drops unknown
keys, coerces obvious scalar types, and then validates the payload with
`NeedAnalysisProfile`. If validation fails, the pipeline triggers the OpenAI
JSON repair helper and re-runs validation on the repaired payload. Finally,
`normalize_profile` cleans strings, deduplicates list values, and harmonises
country/language codes. New aliases belong in `core/schema.py::ALIASES` to keep
legacy inputs working consistently across UI, exports, and the schema.

**DE:** Alle Ingestion-Pfade müssen Rohdaten vor dem Speichern in
`st.session_state["profile"]` durch `coerce_and_fill` schicken. Der Helfer
wendet die `ALIASES`-Zuordnung an (z. B. `company.logo` → `company.logo_url`),
entfernt unbekannte Keys, wandelt offensichtliche Skalartypen und validiert das
Payload anschließend mit `NeedAnalysisProfile`. Schlägt die Validierung fehl,
startet der Prozess die OpenAI-JSON-Reparatur und validiert die korrigierten
Daten erneut. Zum Schluss sorgt `normalize_profile` für saubere Strings,
deduplizierte Listen sowie harmonisierte Länder- und Sprachcodes. Neue Aliasse
gehören in `core/schema.py::ALIASES`, damit Legacy-Inputs in UI, Exporten und
Schema konsistent bleiben.
