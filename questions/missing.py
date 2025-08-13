"""Utilities to detect missing fields in job descriptions."""

from __future__ import annotations

from typing import Any

from core.schema import ALL_FIELDS, VacalyserJD


def missing_fields(jd: VacalyserJD) -> list[str]:
    """Return schema fields that are still empty in ``jd``.

    Args:
        jd: Parsed job description data.

    Returns:
        List of field names whose value is an empty string or list. The
        order matches :data:`core.schema.ALL_FIELDS` to ensure determinism.
    """

    defaults = VacalyserJD()
    missing: list[str] = []
    for field in ALL_FIELDS:
        cursor: Any = jd
        default_cursor: Any = defaults
        for part in field.split("."):
            cursor = getattr(cursor, part)
            default_cursor = getattr(default_cursor, part)
        value = cursor
        default_val = default_cursor
        if value == default_val:
            missing.append(field)
    return missing
