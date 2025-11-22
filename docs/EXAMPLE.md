# Example input & output

The wizard accepts PDFs, DOCX files, or pasted text. Below is a short text snippet similar to what you might paste on the first page, followed by an excerpt of the structured NeedAnalysisProfile JSON you can download from the Summary step.

## Sample job-ad snippet

```
Data Analyst (m/f/d)
Berlin or remote in Germany

You will build dashboards for product and marketing, maintain our Snowflake models, and partner with stakeholders on A/B tests.
We work hybrid (2 days on-site) and offer a learning budget plus flexible hours.

Must-haves
- 3+ years in analytics
- SQL, Python, dbt, Tableau/Looker
- Experience with experimentation design

Nice-to-have
- Experience in B2C marketplace environments
- German language (B1+)
```

## Resulting JSON excerpt

```json
{
  "position": {
    "job_title": "Data Analyst",
    "seniority_level": "mid",
    "team_structure": "Product Analytics"
  },
  "company": {
    "name": "Example GmbH",
    "contact_email": "jobs@example.com"
  },
  "location": {
    "primary_city": "Berlin",
    "country": "Germany",
    "onsite_ratio": "Hybrid (2 days on-site per week)"
  },
  "responsibilities": {
    "items": [
      "Build dashboards for product and marketing",
      "Maintain Snowflake models and A/B test pipelines",
      "Partner with stakeholders on experiment design"
    ]
  },
  "requirements": {
    "hard_skills_required": ["SQL", "Python", "dbt"],
    "hard_skills_optional": ["Tableau", "Looker"],
    "soft_skills_required": ["Stakeholder management"],
    "tools_and_technologies": ["Snowflake"],
    "languages_required": ["German (B1+)"]
  },
  "compensation": {
    "salary_provided": true,
    "salary_min": 65000,
    "salary_max": 80000,
    "currency": "EUR",
    "period": "year",
    "variable_pay": false,
    "bonus_percentage": null,
    "commission_structure": null,
    "equity_offered": false,
    "benefits": ["Learning budget", "Flexible hours"]
  },
  "process": {
    "interview_stages": 3,
    "notes": "Partner interviews plus product case study"
  }
}
```

Use this as a reference for how responsibilities, required/optional skills, languages, and compensation fields are structured. You can download the full JSON from the Summary step or feed it into exports (job ad, interview guide, Boolean search).
