"""Helper validators shared across schema modules."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def deduplicate_preserve_order(value: object) -> list[str]:
    """Return ``value`` as a list of unique strings, preserving the original order."""

    if value is None:
        return []
    if isinstance(value, str):
        candidate_iter: Iterable[Any] = [value]
    elif isinstance(value, Mapping):
        candidate_iter = list(value.values())
    elif isinstance(value, Iterable):
        candidate_iter = value  # type: ignore[assignment]
    else:
        return []

    seen: set[str] = set()
    result: list[str] = []
    for item in candidate_iter:
        if item is None:
            continue
        as_str = str(item).strip()
        if not as_str:
            continue
        marker = as_str.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        result.append(as_str)
    return result


def ensure_canonical_keys(mapping: Mapping[str, Any] | None, canonical: Iterable[str], *, context: str) -> None:
    """Ensure ``mapping`` only uses keys contained in ``canonical``."""

    if not mapping:
        return
    allowed = set(canonical)
    invalid = sorted(key for key in mapping if key not in allowed)
    if invalid:
        raise ValueError(f"{context} contains unsupported keys: {', '.join(invalid)}")
