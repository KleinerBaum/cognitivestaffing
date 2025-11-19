"""Date helper utilities shared across wizard sections."""

from __future__ import annotations

import re
from datetime import date
from typing import Any


def parse_timeline_range(value: str | None) -> tuple[date | None, date | None]:
    """Extract ISO date range from ``value`` if present."""

    if not value:
        return (None, None)
    matches = re.findall(r"(\d{4}-\d{2}-\d{2})", value)
    if not matches:
        return (None, None)
    try:
        start = date.fromisoformat(matches[0])
    except ValueError:
        start = None
    end: date | None
    if len(matches) >= 2:
        try:
            end = date.fromisoformat(matches[1])
        except ValueError:
            end = None
    else:
        end = start
    return (start, end)


def timeline_default_range(value: str | None) -> tuple[date, date]:
    """Return default start/end dates for the recruitment timeline widget."""

    start, end = parse_timeline_range(value)
    today = date.today()
    start = start or today
    end = end or start
    if end < start:
        start, end = end, start
    return start, end


def default_date(value: Any, *, fallback: date | None = None) -> date:
    """Return a ``date`` for widgets, parsing ISO strings when possible."""

    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    if fallback is not None:
        return fallback
    return date.today()


def normalize_date_selection(value: Any) -> tuple[date | None, date | None]:
    """Normalize ``st.date_input`` return value to a ``(start, end)`` tuple."""

    if isinstance(value, date):
        return value, value
    if isinstance(value, (list, tuple)):
        dates = [item for item in value if isinstance(item, date)]
        if len(dates) >= 2:
            return dates[0], dates[1]
        if dates:
            return dates[0], dates[0]
    return None, None


__all__ = [
    "default_date",
    "normalize_date_selection",
    "parse_timeline_range",
    "timeline_default_range",
]
