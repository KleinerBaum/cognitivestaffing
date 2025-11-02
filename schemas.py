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

VACANCY_EXTRACTION_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "VacancyExtraction",
    "type": "object",
    "additionalProperties": False,
    "required": ["language", "role", "company", "skills", "responsibilities"],
    "properties": {
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
        "company": {
            "type": "object",
            "additionalProperties": False,
            "required": ["name"],
            "properties": {
                "name": {"type": "string", "minLength": 1},
                "website": {"type": "string", "format": "uri"},
                "location": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "city": {"type": "string"},
                        "country_code": {"type": "string", "pattern": "^[A-Z]{2}$"},
                    },
                },
            },
        },
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
        "responsibilities": {"type": "array", "items": {"type": "string"}, "minItems": 1},
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
    },
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
    # The Responses API rejects schemas without explicit top-level
    # ``additionalProperties: false``.
    "additionalProperties": False,
    "required": ["language", "guide"],
    "properties": {
        "language": {"type": "string", "pattern": "^[a-z]{2}(-[A-Z]{2})?$"},
        "guide": {
            "type": "object",
            "additionalProperties": False,
            "required": ["intro", "competencies", "questions", "scoring"],
            "properties": {
                "intro": {"type": "string"},
                "competencies": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["name", "weight"],
                        "properties": {
                            "name": {"type": "string"},
                            "weight": {"type": "number", "minimum": 0, "maximum": 1},
                        },
                    },
                },
                "questions": {
                    "type": "array",
                    "minItems": 6,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["id", "text", "type", "competency", "score_max", "evaluation_criteria"],
                        "properties": {
                            "id": {"type": "string"},
                            "text": {"type": "string"},
                            "type": {"type": "string", "enum": ["general", "technical", "behavioral", "cultural"]},
                            "competency": {"type": "string"},
                            "probing": {"type": "array", "items": {"type": "string"}},
                            "evaluation_criteria": {"type": "array", "items": {"type": "string"}, "minItems": 2},
                            "score_max": {"type": "integer", "minimum": 1, "maximum": 10},
                            "red_flags": {"type": "array", "items": {"type": "string"}},
                        },
                    },
                },
                "scoring": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["overall_scale", "rubric_levels"],
                    "properties": {
                        "overall_scale": {"type": "string"},
                        "rubric_levels": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["poor", "average", "good", "excellent"],
                            "properties": {
                                "poor": {"type": "string"},
                                "average": {"type": "string"},
                                "good": {"type": "string"},
                                "excellent": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
    },
}
