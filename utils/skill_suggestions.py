"""Parsing helpers for skill suggestion JSON payloads."""

from __future__ import annotations

from typing import Any, Mapping

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from llm.json_repair import repair_json_payload
from utils.json_repair import JsonRepairResult, JsonRepairStatus, parse_json_with_repair


def _format_schema_error(error: ValidationError) -> str:
    path = ".".join(str(segment) for segment in error.absolute_path) or "<root>"
    return f"{path}: {error.message}"


def parse_skill_suggestions_payload(
    raw: str,
    *,
    schema_name: str,
    schema: Mapping[str, Any],
    allow_llm_repair: bool = True,
) -> JsonRepairResult:
    """Return a validated skill suggestion payload parsed from ``raw``."""

    initial_result = parse_json_with_repair(raw)
    payload = initial_result.payload
    status = initial_result.status

    if payload is None and allow_llm_repair:
        repaired = repair_json_payload(raw, schema_name=schema_name, schema=schema)
        if repaired is not None:
            payload = repaired
            status = JsonRepairStatus.REPAIRED

    if payload is None:
        return JsonRepairResult(payload=None, status=JsonRepairStatus.FAILED, issues=initial_result.issues)

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda err: list(err.path))
    if errors:
        details = "; ".join(_format_schema_error(error) for error in errors[:5])
        if len(errors) > 5:
            details = f"{details} (+{len(errors) - 5} more)"
        raise ValueError(f"Skill suggestion JSON does not match schema: {details}")

    return JsonRepairResult(payload=payload, status=status, issues=initial_result.issues)


__all__ = ["parse_skill_suggestions_payload"]
