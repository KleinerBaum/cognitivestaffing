# JSON Extraction Pipeline

Vacalyser extracts job information into a strict schema so downstream tools can rely on stable keys.
The canonical schema lives in `core/schema.py` and defines the `VacalyserJD` model.

## Schema
The schema contains 22 fields ordered for prompting:

- job_title
- company_name
- location
- industry
- job_type
- remote_policy
- travel_required
- role_summary
- responsibilities
- hard_skills
- soft_skills
- qualifications
- certifications
- salary_range
- benefits
- reporting_line
- target_start_date
- team_structure
- application_deadline
- seniority_level
- languages_required
- tools_and_technologies

`job_type` values are normalized to one of the canonical categories:
`Full-time`, `Part-time`, `Contract`, `Temporary`, or `Internship`.

Example JSON produced by the pipeline:

```json
{
  "schema_version": "v1.0",
  "job_title": "Software Engineer",
  "company_name": "",
  "location": "",
  "industry": "",
  "job_type": "",
  "remote_policy": "",
  "travel_required": "",
  "role_summary": "",
  "responsibilities": [],
  "hard_skills": [],
  "soft_skills": [],
  "qualifications": "",
  "certifications": [],
  "salary_range": "",
  "benefits": [],
  "reporting_line": "",
  "target_start_date": "",
  "team_structure": "",
  "application_deadline": "",
  "seniority_level": "",
  "languages_required": [],
  "tools_and_technologies": []
}
```

## Prompts
`llm/prompts.py` renders two messages:

- **System** – `You are an extractor. Return ONLY a JSON object with the exact keys provided. Use empty strings for missing values and empty lists for missing arrays. No prose.`
- **User** – lists the fields above and injects the job text plus optional `title` and `url`.

Copy‑paste prompt for manual runs:

```
You are an extractor. Return ONLY a JSON object with the exact keys provided. Use empty strings for missing values and empty lists for missing arrays. No prose.

Extract the following fields and respond with a JSON object containing these keys. If data for a key is missing, use an empty string or empty list.
Fields:
- job_title
- company_name
- location
- industry
- job_type
- remote_policy
- travel_required
- role_summary
- responsibilities
- hard_skills
- soft_skills
- qualifications
- certifications
- salary_range
- benefits
- reporting_line
- target_start_date
- team_structure
- application_deadline
- seniority_level
- languages_required
- tools_and_technologies

Text:
{{JOB_TEXT}}
```

## Fallback Strategy
`llm.client.extract_and_parse` calls the model once with the full prompt. If the response cannot be parsed as JSON it retries with a minimal prompt asking for raw JSON. A failure on the second attempt raises `ExtractionError`.

## Extending
To add new fields:

1. Update `ALL_FIELDS` (and `LIST_FIELDS` if it is a list) in `core/schema.py`.
2. Add any prompt handling in `llm/prompts.py`.
3. Re-run tests to ensure the schema and prompts stay in sync.
