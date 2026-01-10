"""Utility functions for loading JSON configuration files."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent


@lru_cache(maxsize=64)
def _load_json_cached(name: str) -> Any:
    with (ROOT / name).open("r", encoding="utf-8") as f:
        return json.load(f)


def load_json(name: str, fallback: Any = None) -> Any:
    """Load a JSON file from the project root.

    Args:
        name: Filename of the JSON file located in the project root.
        fallback: Value to return if loading fails.

    Returns:
        Parsed JSON content or the provided ``fallback`` when loading fails.
    """
    try:
        return _load_json_cached(name)
    except Exception as exc:  # pragma: no cover - defensive
        logging.warning("Failed to load %s: %s", name, exc)
        return fallback
