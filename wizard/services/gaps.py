"""Canonical helpers for detecting missing critical fields."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from wizard.missing_fields import get_path_value, is_blank
from wizard.types import LocalizedText

Validator = Callable[[str | None], tuple[str | None, LocalizedText | None]]


def load_critical_fields() -> tuple[str, ...]:
    """Load critical field paths from ``critical_fields.json``."""

    root = Path(__file__).resolve().parents[2]
    with (root / "critical_fields.json").open("r", encoding="utf-8") as file:
        payload = json.load(file)
    raw_fields = payload.get("critical", [])
    return tuple(field for field in raw_fields if isinstance(field, str))


def field_is_contextually_optional(field: str, profile_data: Mapping[str, object]) -> bool:
    """Return ``True`` when a field can be skipped given the current context."""

    work_policy = str(get_path_value(profile_data, "employment.work_policy") or "").strip().lower()
    travel_required = get_path_value(profile_data, "employment.travel_required")

    if field == "location.primary_city" and work_policy == "remote":
        return True

    if field.startswith("employment.travel_") and travel_required is not True:
        return True

    return False


def _resolve_raw_string(
    profile: Mapping[str, object],
    field: str,
    *,
    field_values: Mapping[str, object] | None = None,
) -> str | None:
    if field_values is not None:
        raw_value = field_values.get(field)
        if isinstance(raw_value, str):
            return raw_value
    profile_value = get_path_value(profile, field)
    if isinstance(profile_value, str):
        return profile_value
    return None


def detect_missing_critical_fields(
    profile: Mapping[str, object],
    *,
    critical_fields: Sequence[str] | None = None,
    field_values: Mapping[str, object] | None = None,
    followups: Sequence[Mapping[str, object]] | None = None,
    max_section: int | None = None,
    section_resolver: Callable[[str], int] | None = None,
    field_validators: Mapping[str, Validator] | None = None,
    profile_refresher: Callable[[], Mapping[str, object]] | None = None,
) -> list[str]:
    """Return critical fields missing from the supplied profile data."""

    resolved_fields = critical_fields or load_critical_fields()
    working_profile = profile
    missing: list[str] = []

    if max_section is not None and section_resolver is None:
        raise ValueError("section_resolver is required when max_section is set")

    for field in resolved_fields:
        if field_is_contextually_optional(field, working_profile):
            continue
        if max_section is not None and section_resolver is not None:
            if section_resolver(field) > max_section:
                continue
        validator = field_validators.get(field) if field_validators else None
        if validator is not None:
            raw_value = _resolve_raw_string(working_profile, field, field_values=field_values)
            validator(raw_value)
            if profile_refresher is not None:
                working_profile = profile_refresher()
        value: object | None
        if field_values is not None and field in field_values:
            value = field_values.get(field)
        else:
            value = get_path_value(working_profile, field)
        if isinstance(value, str):
            value = value.strip()
        if is_blank(value):
            missing.append(field)

    for question in followups or []:
        if not isinstance(question, Mapping):
            continue
        if question.get("priority") != "critical":
            continue
        followup_field = question.get("field")
        if isinstance(followup_field, str) and followup_field:
            missing.append(followup_field)

    return list(dict.fromkeys(missing))


__all__ = [
    "detect_missing_critical_fields",
    "field_is_contextually_optional",
    "load_critical_fields",
]
