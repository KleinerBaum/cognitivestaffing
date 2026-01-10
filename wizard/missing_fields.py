"""Utilities for identifying missing values in profile data."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


# GREP:GET_PATH_VALUE_V1


def get_path_value(profile: Any, dotted_path: str) -> Any:
    """Return the value for ``dotted_path`` in ``profile`` when present."""

    if not dotted_path:
        return profile

    target: Any = profile
    for part in dotted_path.split("."):
        if isinstance(target, Mapping):
            target = target.get(part)
            continue
        if hasattr(target, part):
            target = getattr(target, part)
            continue
        return None
    return target


def is_blank(value: Any) -> bool:
    """Return ``True`` when ``value`` should be treated as missing."""

    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


# GREP:MISSING_FIELDS_V1


def missing_fields(profile: Any, paths: Iterable[str]) -> list[str]:
    """Return the subset of ``paths`` that are blank or missing in ``profile``."""

    missing: list[str] = []
    for path in paths:
        value = get_path_value(profile, path)
        if is_blank(value):
            missing.append(path)
    return missing
