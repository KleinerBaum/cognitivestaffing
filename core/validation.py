"""Validation helpers for placeholder detection and normalization."""

from __future__ import annotations

from typing import Final

# ``PLACEHOLDER`` is part of the identifier on purpose –
# these sentinel tokens mark user inputs that are clearly
# placeholders so downstream logic can flag them. [PLH_SWEEP_GENERIC]
PLACEHOLDER_SENTINELS: Final[set[str]] = {
    "",
    "-",
    "?",
    "k.a.",
    "kein",
    "keine",
    "na",
    "n/a",
    "none",
    "null",
    "tbd",
    "to be defined",
    "unknown",
}


def is_placeholder(value: object | None) -> bool:
    """Return ``True`` if *value* represents a placeholder sentinel."""

    if value is None:
        return True
    normalized = str(value).strip().casefold()
    return normalized in PLACEHOLDER_SENTINELS
