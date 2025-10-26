from typing import Any

from models.need_analysis import NeedAnalysisProfile
from .schema import ALL_FIELDS, ALIASES, LIST_FIELDS, coerce_and_fill


def to_session_state(profile: NeedAnalysisProfile, ss: dict) -> None:
    """Populate session state dict with values from a NeedAnalysisProfile object."""

    def _get(path: str) -> Any:
        cursor: Any = profile
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
            if target != "responsibilities.items":
                parts_list: list[str] = []
                for line_val in value.splitlines():
                    for piece in line_val.split(","):
                        cleaned = piece.strip()
                        if cleaned:
                            parts_list.append(cleaned)
                value = parts_list
            else:
                value = [line.strip() for line in value.splitlines() if line.strip()]
        parts = target.split(".")
        cursor = data
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = value
    return coerce_and_fill(data)
