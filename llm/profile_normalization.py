"""Shared helpers for cleaning LLM profile payloads."""

from __future__ import annotations

from collections.abc import MutableMapping, Sequence
from typing import Any


def _coerce_stage_value(candidate: Any) -> int | None:
    """Return an integer for ``candidate`` when possible."""

    if isinstance(candidate, bool):
        return None
    if isinstance(candidate, int):
        return candidate
    if isinstance(candidate, str):
        stripped = candidate.strip()
        if not stripped:
            return None
        try:
            return int(stripped)
        except ValueError:
            return None
    return None


def _normalise_stage_list(values: Sequence[Any]) -> int | None:
    """Return a sanitized interview stage count from ``values``."""

    if not values:
        return None

    for entry in values:
        maybe_int = _coerce_stage_value(entry)
        if maybe_int is not None:
            return maybe_int

    return len(values)


def normalize_interview_stages_field(payload: MutableMapping[str, Any]) -> None:
    """Mutate ``payload`` so ``process.interview_stages`` is never a list."""

    process = payload.get("process")
    if not isinstance(process, MutableMapping):
        return

    stages = process.get("interview_stages")
    if isinstance(stages, Sequence) and not isinstance(stages, (str, bytes, bytearray)):
        process["interview_stages"] = _normalise_stage_list(list(stages))


__all__ = ["normalize_interview_stages_field"]
