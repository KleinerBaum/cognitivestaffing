"""Utilities to detect missing fields in job descriptions."""

from __future__ import annotations

from core.schema import ALL_FIELDS, LIST_FIELDS, VacalyserJD


def missing_fields(jd: VacalyserJD) -> list[str]:
    """Return schema fields that are still empty in ``jd``.

    Args:
        jd: Parsed job description data.

    Returns:
        List of field names whose value is an empty string or list. The
        order matches :data:`core.schema.ALL_FIELDS` to ensure determinism.
    """

    missing: list[str] = []
    for field in ALL_FIELDS:
        value = getattr(jd, field)
        if field in LIST_FIELDS:
            if not value:
                missing.append(field)
        else:
            if not value:
                missing.append(field)
    return missing
