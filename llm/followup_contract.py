"""Canonical follow-up schema, validation, and normalization helpers."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Mapping, Sequence

from jsonschema.validators import Draft202012Validator

from core.schema_registry import get_followup_response_json_schema

LEGACY_TO_CANONICAL_FIELD_MAP: dict[str, str] = {
    "position.location": "location.primary_city",
    "position.context": "position.role_summary",
    "compensation.salary_range": "compensation.salary_min",
}


@lru_cache(maxsize=1)
def get_followup_json_schema() -> dict[str, Any]:
    """Return the canonical follow-up JSON schema payload."""

    return get_followup_response_json_schema()


@lru_cache(maxsize=1)
def get_followup_validator() -> Draft202012Validator:
    """Return a cached JSON schema validator for follow-up responses."""

    return Draft202012Validator(get_followup_json_schema()["schema"])


def canonicalize_followup_field_path(field: str) -> str:
    """Map legacy follow-up field paths to canonical schema paths."""

    normalized = str(field or "").strip()
    return LEGACY_TO_CANONICAL_FIELD_MAP.get(normalized, normalized)


def normalize_followup_question(item: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return a schema-compliant question entry or ``None`` when invalid."""

    field = canonicalize_followup_field_path(str(item.get("field") or "").strip())
    question = str(item.get("question") or "").strip()
    if not field or not question:
        return None

    priority = str(item.get("priority") or "normal").strip() or "normal"
    suggestions_raw = item.get("suggestions")
    suggestions: list[str] = []
    if isinstance(suggestions_raw, list):
        cleaned_suggestions: list[str] = []
        for suggestion in suggestions_raw:
            if isinstance(suggestion, Mapping):
                text = str(suggestion.get("label") or suggestion.get("name") or "").strip()
            else:
                text = str(suggestion).strip()
            if text:
                cleaned_suggestions.append(text)
        suggestions = cleaned_suggestions
    if not suggestions:
        suggestions = [question]

    result: dict[str, Any] = {
        "field": field,
        "question": question,
        "priority": priority,
        "suggestions": suggestions,
    }

    depends_on_raw = item.get("depends_on")
    if isinstance(depends_on_raw, list):
        depends_on_clean = [str(value).strip() for value in depends_on_raw if str(value).strip()]
        if depends_on_clean:
            result["depends_on"] = depends_on_clean

    rationale = item.get("rationale")
    if isinstance(rationale, str) and rationale.strip():
        result["rationale"] = rationale.strip()

    return result


def dedupe_followup_questions_by_field(questions: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate follow-up entries by field path while preserving order."""

    deduplicated: list[dict[str, Any]] = []
    seen_fields: set[str] = set()
    for question in questions:
        field = str(question.get("field") or "").strip()
        if not field or field in seen_fields:
            continue
        seen_fields.add(field)
        deduplicated.append(question)
    return deduplicated


__all__ = [
    "LEGACY_TO_CANONICAL_FIELD_MAP",
    "canonicalize_followup_field_path",
    "dedupe_followup_questions_by_field",
    "get_followup_json_schema",
    "get_followup_validator",
    "normalize_followup_question",
]
