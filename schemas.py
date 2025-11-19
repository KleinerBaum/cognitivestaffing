from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


def _load_json_schema(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as schema_file:
        return json.load(schema_file)


_NEED_ANALYSIS_SCHEMA_PATH = Path(__file__).resolve().parent / "schema" / "need_analysis.schema.json"
NEED_ANALYSIS_SCHEMA: dict[str, Any] = _load_json_schema(_NEED_ANALYSIS_SCHEMA_PATH)
_NEED_ANALYSIS_PROPERTIES: dict[str, Any] = deepcopy(NEED_ANALYSIS_SCHEMA.get("properties", {}))


SKILL_ENTRY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name"],
    "properties": {
        "name": {"type": "string"},
        "normalized_name": {"type": "string"},
        "esco_uri": {"type": "string"},
        "weight": {"type": "number", "minimum": 0, "maximum": 1},
    },
}

SKILL_ARRAY_SCHEMA = {
    "type": "array",
    "items": SKILL_ENTRY_SCHEMA,
}

_VACANCY_PROPERTIES: dict[str, Any] = {
    "language": {"type": "string", "pattern": "^[a-z]{2}(-[A-Z]{2})?$"},
    "source": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "type": {"type": "string", "enum": ["url", "pdf", "text", "manual"]},
            "url": {"type": "string", "format": "uri"},
            "collected_at": {"type": "string", "format": "date-time"},
        },
    },
}
_VACANCY_PROPERTIES.update(deepcopy(_NEED_ANALYSIS_PROPERTIES))

_VACANCY_PROPERTIES.update(
    {
        "role": {
            "type": "object",
            "additionalProperties": False,
            "required": ["title"],
            "properties": {
                "title": {"type": "string", "minLength": 2},
                "department": {"type": "string"},
                "team": {"type": "string"},
                "seniority": {
                    "type": "string",
                    "enum": ["junior", "mid", "senior", "lead", "principal", "head", "director"],
                },
                "employment_type": {
                    "type": "string",
                    "enum": ["full_time", "part_time", "contract", "temp", "intern", "working_student", "freelancer"],
                },
                "work_policy": {"type": "string", "enum": ["onsite", "hybrid", "remote"]},
                "travel_required_percent": {"type": "number", "minimum": 0, "maximum": 100},
                "relocation": {"type": "boolean"},
                "remote_timezone": {"type": "string"},
                "team_structure": {"type": "string"},
                "reporting_line": {"type": "string"},
                "reporting_manager_name": {"type": "string"},
                "role_summary": {"type": "string"},
                "occupation_label": {"type": "string"},
                "occupation_uri": {"type": "string"},
                "occupation_group": {"type": "string"},
                "supervises": {"type": "integer"},
                "performance_indicators": {"type": "string"},
                "decision_authority": {"type": "string"},
                "key_projects": {"type": "string"},
                "team_size": {"type": "integer"},
                "customer_contact_required": {"type": "boolean"},
                "customer_contact_details": {"type": "string"},
            },
        },
        "experience": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "years_min": {"type": "number", "minimum": 0},
                "years_max": {"type": "number", "minimum": 0},
            },
        },
        "compensation": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "currency": {"type": "string", "pattern": "^[A-Z]{3}$"},
                "period": {"type": "string", "enum": ["year", "month", "hour"]},
                "salary_provided": {"type": "boolean"},
                "salary_min": {"type": "number", "minimum": 0},
                "salary_max": {"type": "number", "minimum": 0},
                "variable_pay": {"type": "boolean"},
                "bonus_percentage": {"type": "number"},
                "commission_structure": {"type": "string"},
                "equity_offered": {"type": "boolean"},
                "benefits": {"type": "array", "items": {"type": "string"}},
                "min": {"type": "number", "minimum": 0},
                "max": {"type": "number", "minimum": 0},
                "bonus": {"type": "string"},
                "equity": {"type": "string"},
            },
        },
        "languages": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["code"],
                "properties": {
                    "code": {"type": "string", "pattern": "^[a-z]{2}(-[A-Z]{2})?$"},
                    "level": {"type": "string", "enum": ["A1", "A2", "B1", "B2", "C1", "C2", "native"]},
                },
            },
        },
        "skills": {
            "type": "object",
            "additionalProperties": False,
            "required": ["must_have", "nice_to_have"],
            "properties": {
                "must_have": {
                    "minItems": 0,
                    **SKILL_ARRAY_SCHEMA,
                },
                "nice_to_have": SKILL_ARRAY_SCHEMA,
            },
        },
        "technologies": SKILL_ARRAY_SCHEMA,
        "benefits": {"type": "array", "items": {"type": "string"}},
        "education": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "degree": {"type": "string"},
                "fields_of_study": {"type": "array", "items": {"type": "string"}},
                "certifications": {"type": "array", "items": {"type": "string"}},
            },
        },
        "esco": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "occupation_label": {"type": "string"},
                "occupation_uri": {"type": "string"},
                "essential_skills": {"type": "array", "items": {"type": "string"}},
            },
        },
        "links": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "application_url": {"type": "string", "format": "uri"},
                "jd_url": {"type": "string", "format": "uri"},
            },
        },
        "constraints": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"visa_sponsorship": {"type": "boolean"}, "sensitive_data": {"type": "boolean"}},
        },
        "notes": {"type": "array", "items": {"type": "string"}},
    }
)

_company_schema = _VACANCY_PROPERTIES.get("company")
if isinstance(_company_schema, dict):
    _company_props = _company_schema.setdefault("properties", {})
    _company_props["location"] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "city": {"type": "string"},
            "country_code": {"type": "string", "pattern": "^[A-Z]{2}$"},
        },
    }

VACANCY_EXTRACTION_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "VacancyExtraction",
    "type": "object",
    "additionalProperties": False,
    "required": ["language", "role", "company", "skills", "responsibilities"],
    "properties": _VACANCY_PROPERTIES,
}

FOLLOW_UPS_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "FollowUpQuestions",
    "type": "object",
    "additionalProperties": False,
    "required": ["questions"],
    "properties": {
        "questions": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["field", "question", "priority"],
                "properties": {
                    "field": {"type": "string", "minLength": 1},
                    "question": {"type": "string", "minLength": 5},
                    "priority": {"type": "string", "enum": ["critical", "normal", "optional"]},
                    "suggestions": {"type": "array", "items": {"type": "string"}},
                    "rationale": {"type": "string"},
                    "depends_on": {"type": "array", "items": {"type": "string"}},
                },
            },
        }
    },
}

PROFILE_SUMMARY_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "CandidateProfileSummary",
    "type": "object",
    "additionalProperties": False,
    "required": ["language", "candidate", "summary_text", "skills"],
    "properties": {
        "language": {"type": "string", "pattern": "^[a-z]{2}(-[A-Z]{2})?$"},
        "candidate": {
            "type": "object",
            "additionalProperties": False,
            "required": ["id"],
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "contact": {"type": "string"},
                "location": {"type": "string"},
                "current_title": {"type": "string"},
                "total_years_experience": {"type": "number", "minimum": 0},
                "links": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "cv_url": {"type": "string", "format": "uri"},
                        "profile_url": {"type": "string", "format": "uri"},
                    },
                },
                "last_updated": {"type": "string", "format": "date-time"},
            },
        },
        "summary_text": {"type": "string"},
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name"],
                "properties": {
                    "name": {"type": "string"},
                    "level": {"type": "string"},
                    "years": {"type": "number", "minimum": 0},
                },
            },
        },
        "languages": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "code": {"type": "string", "pattern": "^[a-z]{2}(-[A-Z]{2})?$"},
                    "level": {"type": "string", "enum": ["A1", "A2", "B1", "B2", "C1", "C2", "native"]},
                },
            },
        },
        "education": {"type": "array", "items": {"type": "string"}},
        "certifications": {"type": "array", "items": {"type": "string"}},
        "fit_notes": {"type": "array", "items": {"type": "string"}},
    },
}

CANDIDATE_MATCHES_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "CandidateMatches",
    "type": "object",
    "additionalProperties": False,
    "required": ["vacancy_id", "candidates"],
    "properties": {
        "vacancy_id": {"type": "string"},
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["candidate_id", "score"],
                "properties": {
                    "candidate_id": {"type": "string"},
                    "name": {"type": "string"},
                    "score": {"type": "number", "minimum": 0, "maximum": 100},
                    "highlighted_skills": {"type": "array", "items": {"type": "string"}},
                    "gaps": {"type": "array", "items": {"type": "string"}},
                    "reasons": {"type": "array", "items": {"type": "string"}},
                    "source": {"type": "string", "enum": ["vector", "manual", "ats", "web"]},
                    "source_refs": {"type": "array", "items": {"type": "string"}},
                    "compliance_flags": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "meta": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"generated_at": {"type": "string", "format": "date-time"}, "model": {"type": "string"}},
        },
    },
}

JOB_AD_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "JobAd",
    "type": "object",
    "additionalProperties": False,
    "required": ["language", "ad"],
    "properties": {
        "language": {"type": "string", "pattern": "^[a-z]{2}(-[A-Z]{2})?$"},
        "metadata": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "tone": {"type": "string", "enum": ["professional", "friendly", "enthusiastic", "formal", "inclusive"]},
                "target_audience": {"type": "string"},
            },
        },
        "ad": {
            "type": "object",
            "additionalProperties": False,
            "required": ["title", "sections"],
            "properties": {
                "title": {"type": "string", "minLength": 3},
                "subtitle": {"type": "string"},
                "location_line": {"type": "string"},
                "sections": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "overview",
                        "responsibilities",
                        "requirements",
                        "benefits",
                        "how_to_apply",
                        "equal_opportunity_statement",
                    ],
                    "properties": {
                        "overview": {"type": "string"},
                        "responsibilities": {"type": "array", "items": {"type": "string"}, "minItems": 3},
                        "requirements": {"type": "array", "items": {"type": "string"}, "minItems": 3},
                        "benefits": {"type": "array", "items": {"type": "string"}},
                        "compensation_note": {"type": "string"},
                        "how_to_apply": {"type": "string"},
                        "equal_opportunity_statement": {"type": "string"},
                    },
                },
                "tags": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}

INTERVIEW_GUIDE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "InterviewGuide",
    "type": "object",
    "additionalProperties": False,
    "required": ["metadata", "questions", "focus_areas", "evaluation_notes"],
    "properties": {
        "metadata": {
            "type": "object",
            "additionalProperties": False,
            "required": ["language", "heading", "job_title", "audience", "tone"],
            "properties": {
                "language": {"type": "string", "pattern": "^[a-z]{2}(-[A-Z]{2})?$"},
                "heading": {"type": "string"},
                "job_title": {"type": "string"},
                "audience": {"type": "string"},
                "audience_label": {"type": "string"},
                "tone": {"type": "string"},
                "tone_label": {"type": "string"},
                "culture_note": {"type": "string"},
            },
        },
        "questions": {
            "type": "array",
            "minItems": 3,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["question", "focus", "evaluation"],
                "properties": {
                    "question": {"type": "string", "minLength": 1},
                    "focus": {"type": "string"},
                    "evaluation": {"type": "string"},
                },
            },
        },
        "focus_areas": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["label", "items"],
                "properties": {
                    "label": {"type": "string"},
                    "items": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "evaluation_notes": {"type": "array", "items": {"type": "string"}},
        "markdown": {"type": "string"},
    },
}
