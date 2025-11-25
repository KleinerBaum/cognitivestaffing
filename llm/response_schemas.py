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
NEED_ANALYSIS_PROFILE_SCHEMA_NAME = "need_analysis_profile"
PRE_EXTRACTION_ANALYSIS_SCHEMA_NAME = "pre_extraction_analysis"
FOLLOW_UP_QUESTIONS_SCHEMA_NAME = "FollowUpQuestions"


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


def _assert_responses_schema_valid(schema: Mapping[str, Any], *, path: str = "$") -> None:
    """Raise ``ValueError`` if any object declares partial ``required`` keys."""

    if not isinstance(schema, Mapping):
        return

    if schema.get("type") == "object":
        properties = schema.get("properties")
        if isinstance(properties, Mapping):
            required = schema.get("required")
            if required is not None:
                if set(required) != set(properties):
                    missing = sorted(set(properties) - set(required or []))
                    extra = sorted(set(required or []) - set(properties))
                    details = ", ".join(
                        filter(
                            None,
                            [
                                f"missing from required: {', '.join(missing)}" if missing else "",
                                f"unknown required keys: {', '.join(extra)}" if extra else "",
                            ],
                        )
                    ).strip(" ,")
                    raise ValueError(f"Schema '{path}' must list all object properties in required; {details}")
            for key, value in properties.items():
                if isinstance(value, Mapping):
                    _assert_responses_schema_valid(value, path=f"{path}.{key}")

    items = schema.get("items")
    if isinstance(items, Mapping):
        _assert_responses_schema_valid(items, path=f"{path}[*]")

    for composite_key in ("anyOf", "oneOf", "allOf"):
        options = schema.get(composite_key)
        if isinstance(options, list):
            for index, option in enumerate(options):
                if isinstance(option, Mapping):
                    _assert_responses_schema_valid(option, path=f"{path}.{composite_key}[{index}]")


def _sanitize_response_schema(name: str, schema: Mapping[str, Any]) -> dict[str, Any]:
    """Return a schema normalised for Responses compatibility."""

    from core.schema import ensure_responses_json_schema

    sanitized = ensure_responses_json_schema(schema)
    _assert_responses_schema_valid(sanitized, path=name)
    return sanitized


def _build_need_analysis_schema() -> Mapping[str, Any]:
    from core.schema import build_need_analysis_responses_schema

    return build_need_analysis_responses_schema()


def _build_followup_schema() -> Mapping[str, Any]:
    from schemas import FOLLOW_UPS_SCHEMA

    return guard_no_additional_properties(deepcopy(FOLLOW_UPS_SCHEMA))


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
    NEED_ANALYSIS_PROFILE_SCHEMA_NAME: _build_need_analysis_schema,
    PRE_EXTRACTION_ANALYSIS_SCHEMA_NAME: lambda: {
        "type": "object",
        "properties": {
            "relevant_fields": {
                "type": "array",
                "description": "Schema field keys that likely have evidence in the text.",
                "items": {"type": "string"},
                "minItems": 0,
            },
            "missing_fields": {
                "type": "array",
                "description": "Schema fields that appear absent or weak in the text.",
                "items": {"type": "string"},
                "minItems": 0,
            },
            "summary": {
                "type": "string",
                "description": "Short notes about the available information in the document.",
            },
        },
        "required": ["relevant_fields", "missing_fields", "summary"],
        "additionalProperties": False,
    },
    FOLLOW_UP_QUESTIONS_SCHEMA_NAME: lambda: _build_followup_schema(),
}


def get_response_schema(name: str) -> dict[str, Any]:
    """Return a validated schema payload for ``name`` from the registry."""

    try:
        schema_factory = _SCHEMA_REGISTRY[name]
    except KeyError as exc:  # pragma: no cover - defensive
        raise KeyError(f"Unknown response schema '{name}'") from exc

    raw_schema = _validate_schema(name, schema_factory())
    return _sanitize_response_schema(name, raw_schema)


def validate_response_schema(name: str, schema: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and return ``schema`` while logging any issues clearly."""

    return _validate_schema(name, schema)


__all__ = [
    "BENEFIT_SUGGESTION_SCHEMA_NAME",
    "TEAM_ADVICE_SCHEMA_NAME",
    "FOLLOW_UP_QUESTIONS_SCHEMA_NAME",
    "NEED_ANALYSIS_PROFILE_SCHEMA_NAME",
    "PRE_EXTRACTION_ANALYSIS_SCHEMA_NAME",
    "INTERVIEW_GUIDE_SCHEMA_NAME",
    "SKILL_SUGGESTION_SCHEMA_NAME",
    "get_response_schema",
    "validate_response_schema",
]
