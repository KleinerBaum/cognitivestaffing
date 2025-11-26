from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, TypedDict

import streamlit as st

from constants.keys import StateKeys


class ContributionRecord(TypedDict, total=False):
    """Metadata describing a single AI contribution."""

    path: str
    value: str | None
    source: str
    model: str | None
    timestamp: str


class AIContributionState(TypedDict):
    """Structured storage for field and list item contributions."""

    fields: dict[str, ContributionRecord]
    items: dict[str, dict[str, ContributionRecord]]


def _now_iso(timestamp: datetime | None = None) -> str:
    """Return an ISO timestamp in UTC."""

    if timestamp is None:
        timestamp = datetime.now(tz=timezone.utc)
    elif timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.isoformat()


def _normalize_timestamp(raw: Any) -> str:
    """Coerce ``raw`` into an ISO timestamp string."""

    if isinstance(raw, datetime):
        return _now_iso(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return _now_iso()
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.isoformat()
    return _now_iso()


def _normalize_entry(path: str, payload: Mapping[str, Any] | None, *, value: str | None = None) -> ContributionRecord:
    """Return a sanitized contribution record."""

    source_raw = (payload or {}).get("source")
    source = str(source_raw).strip() if source_raw else "assistant"
    model_raw = (payload or {}).get("model")
    model = str(model_raw).strip() if model_raw else None
    timestamp_raw = (payload or {}).get("timestamp")

    entry: ContributionRecord = {
        "path": path,
        "value": value,
        "source": source,
        "model": model,
        "timestamp": _normalize_timestamp(timestamp_raw),
    }
    return entry


def _normalize_state(raw: Any) -> AIContributionState:
    """Normalize raw session data into a contribution state."""

    fields_raw = raw.get("fields", {}) if isinstance(raw, Mapping) else {}
    items_raw = raw.get("items", {}) if isinstance(raw, Mapping) else {}

    fields: dict[str, ContributionRecord] = {}
    if isinstance(fields_raw, Mapping):
        for path, payload in fields_raw.items():
            path_str = str(path)
            entry = payload if isinstance(payload, Mapping) else {}
            fields[path_str] = _normalize_entry(path_str, entry)

    items: dict[str, dict[str, ContributionRecord]] = {}
    if isinstance(items_raw, Mapping):
        for path, value_map in items_raw.items():
            path_str = str(path)
            if not isinstance(value_map, Mapping):
                continue
            cleaned: dict[str, ContributionRecord] = {}
            for value, payload in value_map.items():
                value_str = str(value).strip()
                if not value_str:
                    continue
                entry = payload if isinstance(payload, Mapping) else {}
                cleaned[value_str] = _normalize_entry(path_str, entry, value=value_str)
            if cleaned:
                items[path_str] = cleaned

    normalized: AIContributionState = {"fields": fields, "items": items}
    st.session_state[StateKeys.AI_CONTRIBUTIONS] = normalized
    return normalized


def get_ai_contribution_state() -> AIContributionState:
    """Return the normalized AI contribution state from session storage."""

    raw = st.session_state.get(StateKeys.AI_CONTRIBUTIONS, {}) or {}
    return _normalize_state(raw)


def record_field_contribution(
    path: str,
    *,
    source: str = "assistant",
    model: str | None = None,
    timestamp: datetime | None = None,
) -> ContributionRecord:
    """Record a contribution for ``path`` with optional provenance."""

    state = get_ai_contribution_state()
    entry = _normalize_entry(path, {"source": source, "model": model, "timestamp": timestamp})
    state["fields"][path] = entry
    st.session_state[StateKeys.AI_CONTRIBUTIONS] = state
    return entry


def record_list_item_contribution(
    path: str,
    value: str,
    *,
    source: str = "assistant",
    model: str | None = None,
    timestamp: datetime | None = None,
) -> ContributionRecord | None:
    """Record a contribution for a list ``value`` under ``path``."""

    cleaned_value = value.strip()
    if not cleaned_value:
        return None

    state = get_ai_contribution_state()
    items = state.setdefault("items", {})
    path_entries = items.setdefault(path, {})

    normalized_value = cleaned_value
    for existing_value in path_entries:
        if existing_value.casefold() == cleaned_value.casefold():
            normalized_value = existing_value
            break

    entry = _normalize_entry(
        path,
        {"source": source, "model": model, "timestamp": timestamp},
        value=normalized_value,
    )
    path_entries[normalized_value] = entry
    st.session_state[StateKeys.AI_CONTRIBUTIONS] = state
    return entry


def remove_field_contribution(path: str) -> None:
    """Remove contribution metadata for ``path`` and its list entries."""

    state = get_ai_contribution_state()
    state.get("fields", {}).pop(path, None)
    state.get("items", {}).pop(path, None)
    st.session_state[StateKeys.AI_CONTRIBUTIONS] = state


def remove_list_item_contribution(path: str, value: str) -> None:
    """Remove contribution metadata for a list ``value`` under ``path``."""

    state = get_ai_contribution_state()
    cleaned_value = value.strip()
    if not cleaned_value:
        return
    item_map = state.get("items", {}).get(path, {})
    item_map.pop(cleaned_value, None)
    if not item_map:
        state.get("items", {}).pop(path, None)
    st.session_state[StateKeys.AI_CONTRIBUTIONS] = state


def get_field_contribution(path: str) -> ContributionRecord | None:
    """Return contribution metadata for ``path`` when available."""

    state = get_ai_contribution_state()
    return state.get("fields", {}).get(path)


def get_item_contribution(path: str, value: str) -> ContributionRecord | None:
    """Return contribution metadata for a list ``value`` under ``path``."""

    cleaned_value = value.strip()
    if not cleaned_value:
        return None
    state = get_ai_contribution_state()
    return state.get("items", {}).get(path, {}).get(cleaned_value)


__all__ = [
    "AIContributionState",
    "ContributionRecord",
    "get_ai_contribution_state",
    "get_field_contribution",
    "get_item_contribution",
    "record_field_contribution",
    "record_list_item_contribution",
    "remove_field_contribution",
    "remove_list_item_contribution",
]
