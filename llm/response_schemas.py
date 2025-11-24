"""Registry for structured OpenAI response schemas."""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any, Callable, Mapping

from jsonschema import Draft202012Validator, exceptions as jsonschema_exceptions

from core.schema_guard import guard_no_additional_properties

logger = logging.getLogger(__name__)

INTERVIEW_GUIDE_SCHEMA_NAME = "interviewGuide"
SKILL_SUGGESTION_SCHEMA_NAME = "skill_suggestions"
BENEFIT_SUGGESTION_SCHEMA_NAME = "benefit_suggestions"
TEAM_ADVICE_SCHEMA_NAME = "team_advice"


def _validate_schema(name: str, schema: Mapping[str, Any]) -> dict[str, Any]:
    """Return a defensive copy of ``schema`` after validation."""

    schema_copy = deepcopy(dict(schema))

    try:
        Draft202012Validator.check_schema(schema_copy)
    except jsonschema_exceptions.SchemaError as exc:
        logger.error("Schema '%s' is not a valid JSON schema: %s", name, exc)
        raise

    required_fields = list(schema_copy.get("required") or [])
    properties = schema_copy.get("properties") or {}
    missing = [field for field in required_fields if field not in properties]
    if missing:
        message = "Schema '%s' is missing required property definitions: %s" % (name, ", ".join(sorted(missing)))
        logger.error(message)
        raise ValueError(message)

    return schema_copy


def _interview_guide_schema() -> Mapping[str, Any]:
    from models.interview_guide import InterviewGuide

    # The InterviewGuide schema is a list of question blocks that each include the
    # original question, the generated answer, a human-readable label, and
    # optional metadata (e.g., notes). Keeping ``label`` required documents the
    # earlier fix where missing labels caused Responses payload validation to
    # fail.
    return guard_no_additional_properties(InterviewGuide.model_json_schema())


_SCHEMA_REGISTRY: dict[str, Callable[[], Mapping[str, Any]]] = {
    INTERVIEW_GUIDE_SCHEMA_NAME: _interview_guide_schema,
    SKILL_SUGGESTION_SCHEMA_NAME: lambda: {
        "type": "object",
        "properties": {
            "tools_and_technologies": {"type": "array", "items": {"type": "string"}},
            "hard_skills": {"type": "array", "items": {"type": "string"}},
            "soft_skills": {"type": "array", "items": {"type": "string"}},
            "certificates": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "tools_and_technologies",
            "hard_skills",
            "soft_skills",
            "certificates",
        ],
        "additionalProperties": False,
    },
    BENEFIT_SUGGESTION_SCHEMA_NAME: lambda: {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 5,
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    },
    TEAM_ADVICE_SCHEMA_NAME: lambda: {
        "type": "object",
        "properties": {
            "assistant_message": {"type": "string"},
            "reporting_line_suggestion": {"type": "string"},
            "direct_reports_suggestion": {
                "type": "integer",
                "minimum": 0,
            },
            "follow_up_question": {"type": "string"},
        },
        "required": ["assistant_message"],
        "additionalProperties": False,
    },
}


def get_response_schema(name: str) -> dict[str, Any]:
    """Return a validated schema payload for ``name`` from the registry."""

    try:
        schema_factory = _SCHEMA_REGISTRY[name]
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError(f"Unknown response schema '{name}'") from exc

    return _validate_schema(name, schema_factory())


def validate_response_schema(name: str, schema: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and return ``schema`` while logging any issues clearly."""

    return _validate_schema(name, schema)


__all__ = [
    "BENEFIT_SUGGESTION_SCHEMA_NAME",
    "TEAM_ADVICE_SCHEMA_NAME",
    "INTERVIEW_GUIDE_SCHEMA_NAME",
    "SKILL_SUGGESTION_SCHEMA_NAME",
    "get_response_schema",
    "validate_response_schema",
]
