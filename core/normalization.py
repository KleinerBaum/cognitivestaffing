"""Normalization helpers shared across schema and update pipelines."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

__all__ = [
    "sanitize_optional_url_value",
    "sanitize_optional_url_fields",
]


def sanitize_optional_url_value(value: object) -> str | None:
    """Return a trimmed URL string or ``None`` for blank inputs.

    This guard ensures optional URL fields accept empty strings emitted by UI
    widgets or legacy payloads without tripping Pydantic validation.  # URL_EMPTY_TO_NONE
    """

    if value is None:
        return None
    if isinstance(value, str):
        candidate = value.strip()
    else:
        candidate = str(value).strip()
    return candidate or None


def sanitize_optional_url_fields(data: MutableMapping[str, Any]) -> None:
    """Recursively normalise URL-like keys inside ``data`` in-place.

    The helper trims whitespace around ``*_url``/``*Url`` keys and converts
    empty strings to ``None`` so downstream validation no longer resets the
    profile payload when a user clears the logo field.  # VALIDATION_GUARD
    """

    def _walk(node: Any) -> None:
        if isinstance(node, MutableMapping):
            for key, value in list(node.items()):
                if isinstance(key, str) and key.lower().endswith("url"):
                    node[key] = sanitize_optional_url_value(value)
                if isinstance(value, (MutableMapping, list, tuple)):
                    _walk(value)
        elif isinstance(node, (list, tuple)):
            for item in node:
                _walk(item)

    _walk(data)

