## Schema (NeedAnalysisProfile) / Schema (NeedAnalysisProfile)

**EN:** `NeedAnalysisProfile` groups canonical vacancy data into dedicated sections. The
field names below use the dot-paths from `constants/keys.ProfilePaths`.

- **company:** `name`, `brand_name`, `hq_location`, `industry`, `size`, `website`,
  `mission`, `culture`, `contact_name`, `contact_email`, `contact_phone`,
  `brand_color`, `claim`, `benefits`.
- **position:** `job_title`, `seniority_level`, `department`, `team_structure`,
  `reporting_line`, `reporting_manager_name`, `role_summary`,
  `occupation_label`, `occupation_uri`, `occupation_group`, `key_projects`,
  `team_size`, `supervises`, `performance_indicators`.
- **location:** `primary_city`, `country`, `onsite_ratio`.
- **employment:** `job_type`, `work_policy`, `contract_type`, `work_schedule`,
  `remote_percentage`, `contract_end`, `travel_required`, `travel_share`,
  `travel_regions`, `travel_continents`, `travel_details`, `overtime_expected`,
  `relocation_support`, `relocation_details`, `visa_sponsorship`,
  `security_clearance_required`, `shift_work`.
- **compensation:** `salary_provided`, `salary_min`, `salary_max`, `currency`,
  `period`, `variable_pay`, `bonus_percentage`, `commission_structure`,
  `equity_offered`, `benefits`.
- **responsibilities:** `items`.
- **requirements:** `hard_skills_required`, `hard_skills_optional`,
  `soft_skills_required`, `soft_skills_optional`,
  `tools_and_technologies`, `languages_required`, `languages_optional`,
  `certificates`, `certifications`, `language_level_english`.
- **process:** `interview_stages`, `stakeholders`, `phases`,
  `recruitment_timeline`, `process_notes`, `application_instructions`,
  `onboarding_process`, `hiring_manager_name`, `hiring_manager_role`.
- **meta:** `target_start_date`, `application_deadline`, `followups_answered`.

**DE:** `NeedAnalysisProfile` bündelt kanonische Vakanzdaten in eigenen Abschnitten.
Die Feldnamen unten verwenden die Dot-Pfade aus `constants/keys.ProfilePaths`.

- **company:** `name`, `brand_name`, `hq_location`, `industry`, `size`, `website`,
  `mission`, `culture`, `contact_name`, `contact_email`, `contact_phone`,
  `brand_color`, `claim`, `benefits`.
- **position:** `job_title`, `seniority_level`, `department`, `team_structure`,
  `reporting_line`, `reporting_manager_name`, `role_summary`,
  `occupation_label`, `occupation_uri`, `occupation_group`, `key_projects`,
  `team_size`, `supervises`, `performance_indicators`.
- **location:** `primary_city`, `country`, `onsite_ratio`.
- **employment:** `job_type`, `work_policy`, `contract_type`, `work_schedule`,
  `remote_percentage`, `contract_end`, `travel_required`, `travel_share`,
  `travel_regions`, `travel_continents`, `travel_details`, `overtime_expected`,
  `relocation_support`, `relocation_details`, `visa_sponsorship`,
  `security_clearance_required`, `shift_work`.
- **compensation:** `salary_provided`, `salary_min`, `salary_max`, `currency`,
  `period`, `variable_pay`, `bonus_percentage`, `commission_structure`,
  `equity_offered`, `benefits`.
- **responsibilities:** `items`.
- **requirements:** `hard_skills_required`, `hard_skills_optional`,
  `soft_skills_required`, `soft_skills_optional`,
  `tools_and_technologies`, `languages_required`, `languages_optional`,
  `certificates`, `certifications`, `language_level_english`.
- **process:** `interview_stages`, `stakeholders`, `phases`,
  `recruitment_timeline`, `process_notes`, `application_instructions`,
  `onboarding_process`, `hiring_manager_name`, `hiring_manager_role`.
- **meta:** `target_start_date`, `application_deadline`, `followups_answered`.

**EN:** `company.name` is optional in the structured output schema. When the extractor
cannot infer it from the job ad, the wizard inserts a bilingual follow-up question
instead of rejecting the payload, and the field can be filled later without
breaking validation.

**DE:** `company.name` ist im strukturierten Schema optional. Falls der Extractor den
Namen nicht aus der Anzeige ableiten kann, erstellt der Wizard eine zweisprachige
Follow-up-Frage, statt das Payload abzulehnen; das Feld lässt sich später
ausfüllen, ohne die Validierung zu verletzen.

### Example output / Beispielausgabe

```json
{
  "company": {
    "name": null,
    "brand_name": "TechCorp",
    "hq_location": "Berlin",
    "size": "201-500",
    "website": "https://techcorp.example",
    "mission": "Build data platforms",
    "contact_email": "talent@techcorp.example",
    "brand_color": "#0C1F3D",
    "claim": "Invent tomorrow.",
    "benefits": ["Learning budget", "Mobility stipend"]
  },
  "position": {
    "job_title": "Senior Backend Engineer",
    "seniority_level": "senior",
    "department": "Engineering",
    "team_structure": "Cross-functional squads",
    "reporting_line": "Director of Engineering",
    "role_summary": "Design and operate cloud-native services.",
    "occupation_label": "Software developer",
    "occupation_uri": "https://data.europa.eu/esco/occupation/12345",
    "team_size": 6,
    "performance_indicators": "Deployment frequency, MTTR"
  },
  "location": {
    "primary_city": "Berlin",
    "country": "DE",
    "onsite_ratio": "2 days onsite"
  },
  "responsibilities": {
    "items": [
      "Design scalable APIs",
      "Review pull requests",
      "Mentor engineers"
    ]
  },
  "requirements": {
    "hard_skills_required": ["Python", "Django"],
    "hard_skills_optional": ["Go"],
    "soft_skills_required": ["Collaboration"],
    "soft_skills_optional": ["Facilitation"],
    "tools_and_technologies": ["PostgreSQL", "Docker"],
    "languages_required": ["English"],
    "languages_optional": ["German"],
    "certificates": [],
    "certifications": ["AWS Certified Developer"],
    "language_level_english": "C1"
  },
  "employment": {
    "job_type": "full_time",
    "work_policy": "hybrid",
    "contract_type": "permanent",
    "remote_percentage": 60,
    "travel_required": false,
    "relocation_support": true,
    "visa_sponsorship": true
  },
  "compensation": {
    "salary_provided": true,
    "salary_min": 65000.0,
    "salary_max": 78000.0,
    "currency": "EUR",
    "period": "year",
    "variable_pay": true,
    "bonus_percentage": 10.0,
    "benefits": [
      "Company pension",
      "Wellness stipend"
    ]
  },
  "process": {
    "interview_stages": 3,
    "stakeholders": [
      {
        "name": "Alex Example",
        "role": "Hiring Manager",
        "email": "alex@example.com",
        "primary": true
      }
    ],
    "phases": [
      {
        "name": "Intro call",
        "participants": ["Recruiter"],
        "timeframe": "30 min"
      },
      {
        "name": "Technical deep dive",
        "participants": ["Engineering panel"],
        "task_assignments": "System design"
      }
    ],
    "recruitment_timeline": "Offer target within 4 weeks",
    "application_instructions": "Apply via techcorp.example/careers",
    "hiring_manager_name": "Alex Example",
    "hiring_manager_role": "Director of Engineering"
  },
  "meta": {
    "target_start_date": "2025-02-01",
    "application_deadline": "2025-01-15",
    "followups_answered": [
      "company.contact_email",
      "compensation.salary_min"
    ]
  }
}
```

### Confidence metadata / Confidence-Metadaten

**EN:** Extraction metadata lives in `st.session_state[StateKeys.PROFILE_METADATA]`
(not inside the profile JSON):

- `field_confidence`: maps dot-paths to entries with `tier`, `source`, optional
  `rule_id`, and numeric `score`.
- `rules`: records deterministic enrichment sources (e.g. scraped about pages)
  so the UI can show 🧭 tooltips.
- `llm_fields`: lists values provided by the LLM pipeline.
- `high_confidence_fields` / `locked_fields`: gate edits for authoritative
  values until the user unlocks them.

**DE:** Extraktions-Metadaten liegen in `st.session_state[StateKeys.PROFILE_METADATA]`
(nicht im Profil-JSON):

- `field_confidence`: ordnet Dot-Pfade Einträgen mit `tier`, `source`, optionalem
  `rule_id` und numerischem `score` zu.
- `rules`: protokolliert deterministische Anreicherungen (z. B. About-Seiten),
  damit die UI 🧭-Tooltips anzeigen kann.
- `llm_fields`: listet Werte auf, die vom LLM geliefert wurden.
- `high_confidence_fields` / `locked_fields`: sperren authoritative Werte, bis
  Nutzer:innen sie aktiv freigeben.

## Normalisation & Key Alignment / Normalisierung & Key-Ausrichtung

**EN:** All ingestion routes must pass raw dictionaries through
`core.schema.coerce_and_fill()` before storing them in
`st.session_state[StateKeys.PROFILE]`. The helper applies
`core.schema.ALIASES`, filters unknown keys, coerces scalars, and validates the
payload with `NeedAnalysisProfile`. When validation fails, the pipeline triggers
the JSON repair helper and repeats validation. Afterwards
`utils.normalization.normalize_profile()` trims noise, deduplicates lists,
harmonises countries/languages, and revalidates the cleaned payload. New fields
must be added to `NeedAnalysisProfile` and `ProfilePaths` together; only migrate
historic inputs via `ALIASES`.

**DE:** Alle Ingestion-Pfade schicken Rohdaten vor dem Speichern in
`st.session_state[StateKeys.PROFILE]` durch `core.schema.coerce_and_fill()`. Der
Helfer wendet `core.schema.ALIASES` an, entfernt unbekannte Keys, konvertiert
Skalare und validiert die Daten mit `NeedAnalysisProfile`. Schlägt die
Validierung fehl, startet der Prozess die JSON-Reparatur und validiert erneut.
Anschließend sorgt `utils.normalization.normalize_profile()` für bereinigte
Strings, deduplizierte Listen sowie harmonisierte Länder- und Sprachcodes und
prüft das Payload erneut. Neue Felder gehören gleichzeitig in
`NeedAnalysisProfile` und `ProfilePaths`; historische Eingaben werden nur über
`ALIASES` migriert.
