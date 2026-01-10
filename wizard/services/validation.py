"""Canonical profile validation helpers for wizard and tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from wizard.missing_fields import get_path_value, is_blank
from wizard.services.gaps import detect_missing_critical_fields, load_critical_fields


@dataclass(frozen=True)
class ProfileValidationResult:
    """Structured validation outcome for a profile."""

    ok: bool
    issues: list[str]
    missing_required: list[str]


def is_value_present(value: object | None) -> bool:
    """Return ``True`` when ``value`` should count as populated."""

    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set)):
        return any(is_value_present(item) for item in value)
    if isinstance(value, Mapping):
        return any(is_value_present(item) for item in value.values())
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return True


def _extract_salary_range(profile: Mapping[str, object]) -> tuple[float | int | None, float | int | None]:
    compensation = get_path_value(profile, "compensation")
    if isinstance(compensation, Mapping):
        salary_block = compensation.get("salary")
        if isinstance(salary_block, Mapping):
            minimum = salary_block.get("min")
            maximum = salary_block.get("max")
            return _to_number(minimum), _to_number(maximum)
        minimum = compensation.get("salary_min")
        maximum = compensation.get("salary_max")
        return _to_number(minimum), _to_number(maximum)
    return None, None


def _to_number(value: object | None) -> float | int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _has_location(profile: Mapping[str, object]) -> bool:
    primary_city = get_path_value(profile, "location.primary_city")
    country = get_path_value(profile, "location.country")
    position_location = get_path_value(profile, "position.location")
    return not is_blank(primary_city) or not is_blank(country) or not is_blank(position_location)


def validate_profile(
    profile: Mapping[str, object],
    *,
    jurisdiction: str | None = None,
    required_fields: Sequence[str] | None = None,
) -> ProfileValidationResult:
    """Validate profile content and return structured issues."""

    issues: list[str] = []
    missing_required = detect_missing_critical_fields(
        profile,
        critical_fields=required_fields or load_critical_fields(),
    )

    for field in missing_required:
        issues.append(f"Missing required field: {field}")

    if jurisdiction and not _has_location(profile):
        issues.append(f"Location is required for {jurisdiction} reviews.")

    minimum, maximum = _extract_salary_range(profile)
    if minimum is not None and maximum is not None and minimum > maximum:
        issues.append("Salary minimum cannot exceed maximum.")

    return ProfileValidationResult(ok=not issues, issues=issues, missing_required=missing_required)


__all__ = ["ProfileValidationResult", "is_value_present", "validate_profile"]
