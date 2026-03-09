"""Shared loader for critical field configuration."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def load_critical_fields() -> tuple[str, ...]:
    """Return critical field paths from ``critical_fields.json``.

    The value is cached per-process to guarantee a single source of truth
    across follow-up generation, step gating, router validation and extraction.
    """

    root = Path(__file__).resolve().parents[1]
    with (root / "critical_fields.json").open("r", encoding="utf-8") as file:
        payload = json.load(file)
    raw_fields = payload.get("critical", [])
    return tuple(field for field in raw_fields if isinstance(field, str))


__all__ = ["load_critical_fields"]
