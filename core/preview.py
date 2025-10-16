"""Utilities for building previews of prefilled profile data."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import streamlit as st

from constants.keys import StateKeys
from utils.i18n import tr


SectionEntries = list[tuple[str, list[tuple[str, Any]]]]


def build_prefilled_sections(
    *,
    include_prefixes: Sequence[str] | None = None,
    exclude_prefixes: Sequence[str] = (),
) -> SectionEntries:
    """Return grouped profile entries that already contain data.

    Args:
        include_prefixes: Optional prefixes that must match the beginning of a
            flattened key in order to be considered. If ``None`` all prefixes
            are allowed.
        exclude_prefixes: Prefixes that should be filtered from the result even
            when they match ``include_prefixes``.

    Returns:
        A list of tuples where each tuple represents a section with a localized
        label and a list of ``(path, value)`` entries that contain data.
    """

    include_prefixes = tuple(include_prefixes or ())
    exclude_prefixes = tuple(exclude_prefixes or ())

    profile = st.session_state.get(StateKeys.PROFILE)
    raw_profile = st.session_state.get(StateKeys.EXTRACTION_RAW_PROFILE)

    flattened: dict[str, Any] = {}

    if isinstance(raw_profile, Mapping):
        flattened.update(_flatten(raw_profile))
    if isinstance(profile, Mapping):
        flattened.update(_flatten(profile))

    def _allowed(path: str) -> bool:
        if path.startswith("meta."):
            return False
        if include_prefixes and not any(path.startswith(pref) for pref in include_prefixes):
            return False
        if any(path.startswith(pref) for pref in exclude_prefixes):
            return False
        return _has_value(flattened[path])

    filled = {path: value for path, value in flattened.items() if _allowed(path)}
    if not filled:
        return []

    sections: list[tuple[str, tuple[str, ...]]] = [
        (tr("Unternehmen", "Company"), ("company.",)),
        (
            tr("Basisdaten", "Basic info"),
            ("position.", "location.", "responsibilities."),
        ),
        (tr("Anforderungen", "Requirements"), ("requirements.",)),
        (tr("Beschäftigung", "Employment"), ("employment.",)),
        (
            tr("Leistungen & Benefits", "Rewards & Benefits"),
            ("compensation.",),
        ),
        (tr("Prozess", "Process"), ("process.",)),
    ]

    section_entries: SectionEntries = []
    for label, prefixes in sections:
        if include_prefixes and not any(
            any(candidate.startswith(prefix) for prefix in prefixes) for candidate in include_prefixes
        ):
            continue
        entries = [
            (path, filled[path]) for path in sorted(filled) if any(path.startswith(prefix) for prefix in prefixes)
        ]
        if entries:
            section_entries.append((label, entries))

    return section_entries


def preview_value_to_text(value: Any) -> str:
    """Return a compact textual representation for a preview value."""

    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict)):
        parts = [preview_value_to_text(item) for item in value]
        return ", ".join(part for part in parts if part)
    if isinstance(value, Mapping):
        parts = [preview_value_to_text(item) for item in value.values()]
        return ", ".join(part for part in parts if part)
    return ""


def _flatten(data: Mapping[str, Any] | None, prefix: str = "") -> dict[str, Any]:
    """Convert a nested mapping into a dictionary with dotted paths."""

    if not isinstance(data, Mapping):
        return {}

    items: dict[str, Any] = {}
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, Mapping):
            items.update(_flatten(value, path))
        else:
            items[path] = value
    return items


def _has_value(value: Any) -> bool:
    """Return ``True`` if a flattened value should be shown in the overview."""

    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, dict)):
        return any(_has_value(item) for item in value)
    if isinstance(value, Mapping):
        return any(_has_value(item) for item in value.values())
    return bool(value)


__all__ = ["build_prefilled_sections", "preview_value_to_text"]
