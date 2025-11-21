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
  "role": {
    "title": "Data Analyst",
    "seniority": "mid",
    "department": "Product Analytics"
  },
  "company": {
    "name": "Example GmbH",
    "contact_email": "jobs@example.com"
  },
  "location": {
    "primary_city": "Berlin",
    "work_model": "hybrid",
    "onsite_requirements": "2 days on-site per week"
  },
  "requirements": {
    "hard_skills": [
      "SQL",
      "Python",
      "dbt",
      "Tableau",
      "A/B testing"
    ],
    "soft_skills": ["Stakeholder management"],
    "languages": ["German (B1)"]
  },
  "process": {
    "interview_stages": 3,
    "notes": "Partner interviews plus product case study"
  },
  "benefits": {
    "perks": ["Learning budget", "Flexible hours"],
    "work_life_balance": ["Hybrid"]
  }
}
```

Use this as a reference for how responsibilities, requirements, and benefits are structured. You can download the full JSON from the Summary step or feed it into exports (job ad, interview guide, Boolean search).
