"""Shared helpers for follow-up question bookkeeping."""

from __future__ import annotations

from typing import Any


def followup_has_response(value: Any) -> bool:
    """Return ``True`` if ``value`` represents a provided follow-up answer."""

    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(followup_has_response(item) for item in value)
    return value not in ("", {})


__all__ = ["followup_has_response"]
