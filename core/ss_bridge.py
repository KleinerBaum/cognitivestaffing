from typing import Any

from models.need_analysis import NeedAnalysisProfile
from .schema import ALL_FIELDS, ALIASES, LIST_FIELDS, coerce_and_fill


def to_session_state(jd: NeedAnalysisProfile, ss: dict) -> None:
    """Populate session state dict with values from a NeedAnalysisProfile object."""

    def _get(path: str) -> Any:
        cursor: Any = jd
        for part in path.split("."):
            cursor = getattr(cursor, part)
        return cursor

    for field in ALL_FIELDS:
        value = _get(field)
        if field in LIST_FIELDS:
            ss[field] = "\n".join(value)
        else:
            ss[field] = value
    # Remove deprecated alias keys to avoid duplicates in form
    for alias in ALIASES:
        ss.pop(alias, None)


def from_session_state(ss: dict) -> NeedAnalysisProfile:
    """Build a NeedAnalysisProfile model from the session state values."""
    data: dict[str, Any] = {}
    for key, value in ss.items():
        target = ALIASES.get(key, key)
        if target in LIST_FIELDS and isinstance(value, str):
            value = [line for line in value.splitlines() if line.strip()]
        parts = target.split(".")
        cursor = data
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = value
    return coerce_and_fill(data)
