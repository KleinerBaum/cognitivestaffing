## Schema (v2.1)
Vacalyzer's schema is now hierarchical, grouping related fields for a profile. Each top-level key represents a category (such as `company`, `position`, `compensation`, etc.), containing sub-fields. We focus on core fields (priority 1–3) to gather essential information first. Below are the groups and example fields:
- **company:** `name`, `industry`, `hq_location`, `size`, `website`  
- **position:** `job_title`, `seniority_level`, `department`, `management_scope`, `reporting_line`, `role_summary`, `team_structure`, etc.  
- **employment:** `job_type`, `work_policy` (Onsite/Hybrid/Remote), `travel_required`, `work_schedule`, etc.  
- **compensation:** `salary_currency`, `salary_min`, `salary_max`, `salary_period`, `benefits`, etc.  
- **requirements:** `hard_skills`, `soft_skills`, `tools_and_technologies`, `education_level`, `languages_required`, `certificates` (`certifications`), etc.
- **responsibilities:** `items` (list of key responsibilities), `top3` (the top three responsibilities).  
*(Other groups like contacts, process, and analytics exist in the schema but may not be fully utilized in the initial extraction.)*

All fields are expected in the JSON output, even if empty (empty string for text, empty list for lists). The `schema_version` is "v2.1" indicating the expanded schema.

Example JSON output from the extractor (abridged):
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

### Confidence metadata and locks

The extractor and rule passes attach metadata that the wizard uses to explain
where values came from and whether they should be editable without an explicit
unlock:

- `field_confidence` is a map of dot-paths to metadata objects. Each entry at
  least contains a `tier` (`rule_strong` for deterministic rule hits,
  `ai_assisted` for model output) and a `source` label (`"rule"` or `"llm"`).
  Rule matches also record their pattern identifier as `rule` and a numeric
  `score` describing match confidence. The wizard renders these tiers as icons
  next to each field (🔎 for rule matches, 🤖 for AI) together with a short
  tooltip, and it shows the same legend in the sidebar.
- `high_confidence_fields` enumerates fields that should initially be treated
  as authoritative. Rule-based matches populate this list, and downstream
  heuristics may append additional items (for example locked benefit lists).
- `locked_fields` lists the fields that require a user toggle before editing.
  When a field appears in `high_confidence_fields` or carries the
  `rule_strong` tier the wizard marks it as locked, pre-fills the unlock toggle
  state, and preserves the tooltip from `field_confidence`.

All three structures are stored in `profile_metadata` and persist across
extraction retries so that subsequent runs honour existing locks and
indicators.
