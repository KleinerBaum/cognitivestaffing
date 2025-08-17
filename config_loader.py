"""Utility functions for loading JSON configuration files."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent


def load_json(name: str, fallback: Any = None) -> Any:
    """Load a JSON file from the project root.

    Args:
        name: Filename of the JSON file located in the project root.
        fallback: Value to return if loading fails.

    Returns:
        Parsed JSON content or the provided ``fallback`` when loading fails.
    """
    try:
        with (ROOT / name).open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:  # pragma: no cover - defensive
        logging.warning("Failed to load %s: %s", name, exc)
        return fallback
