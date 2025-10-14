"""Centralised JSON schema definitions for LLM structured outputs."""

from __future__ import annotations

from typing import Any, Final

from models.interview_guide import InterviewGuide
from models.need_analysis import NeedAnalysisProfile

__all__ = [
    "VACANCY_EXTRACTION_SCHEMA",
    "FOLLOW_UPS_SCHEMA",
    "PROFILE_SUMMARY_SCHEMA",
    "CANDIDATE_MATCHES_SCHEMA",
    "JOB_AD_SCHEMA",
    "INTERVIEW_GUIDE_SCHEMA",
]


def _pydantic_schema(model: type) -> dict[str, Any]:
    """Return the JSON schema for a Pydantic model without mutating it."""

    schema = model.model_json_schema()
    # ``title`` is not required for the Responses API schema and keeping it
    # consistent across environments reduces needless diffs in tests.
    schema.pop("title", None)
    return schema


VACANCY_EXTRACTION_SCHEMA: Final[dict[str, Any]] = _pydantic_schema(NeedAnalysisProfile)
INTERVIEW_GUIDE_SCHEMA: Final[dict[str, Any]] = _pydantic_schema(InterviewGuide)

FOLLOW_UPS_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["questions"],
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["field", "question", "priority"],
                "properties": {
                    "field": {"type": "string"},
                    "question": {"type": "string"},
                    "priority": {
                        "type": "string",
                        "enum": ["critical", "normal", "optional"],
                    },
                    "suggestions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                    },
                    "context": {
                        "type": ["string", "null"],
                        "description": "Optional rationale shown to recruiters.",
                    },
                },
            },
        }
    },
}

PROFILE_SUMMARY_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["candidate_id", "language", "summary"],
    "properties": {
        "candidate_id": {"type": "string"},
        "language": {"type": "string"},
        "summary": {"type": "string"},
        "experience_highlights": {
            "type": "array",
            "items": {"type": "string"},
            "default": [],
        },
        "key_skills": {
            "type": "array",
            "items": {"type": "string"},
            "default": [],
        },
        "development_areas": {
            "type": "array",
            "items": {"type": "string"},
            "default": [],
        },
        "recommendations": {
            "type": "array",
            "items": {"type": "string"},
            "default": [],
        },
    },
}

CANDIDATE_MATCHES_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["matches"],
    "properties": {
        "matches": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["candidate_id", "score"],
                "properties": {
                    "candidate_id": {"type": "string"},
                    "score": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 100,
                    },
                    "strengths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                    },
                    "gaps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                    },
                    "notes": {"type": "string"},
                },
            },
        },
        "vacancy_summary": {"type": "string"},
    },
}

JOB_AD_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["language", "headline", "sections", "markdown"],
    "properties": {
        "language": {"type": "string"},
        "tone": {"type": "string"},
        "audience": {"type": "string"},
        "headline": {"type": "string"},
        "company": {
            "type": "object",
            "additionalProperties": False,
            "required": [],
            "properties": {
                "display_name": {"type": "string"},
                "brand_name": {"type": "string"},
                "legal_name": {"type": "string"},
            },
        },
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title"],
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "bullets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": [],
                    },
                },
            },
        },
        "call_to_action": {"type": "string"},
        "markdown": {
            "type": "string",
            "description": "Pre-rendered Markdown for legacy views.",
        },
    },
}
