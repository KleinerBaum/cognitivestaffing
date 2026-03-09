"""Utilities for synchronizing Streamlit widget state and navigation state."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, MutableMapping, Sequence

import streamlit as st

from constants.keys import StateKeys
from wizard.navigation.keys import WizardSessionKeys


def iter_profile_scalars(data: Mapping[str, Any], prefix: str = "") -> Iterable[tuple[str, Any]]:
    """Yield dot-paths for scalar values within ``data``."""

    for key, value in (data or {}).items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, Mapping):
            yield from iter_profile_scalars(value, path)
        elif isinstance(value, (list, tuple, set, frozenset)):
            continue
        else:
            yield path, value


def prime_widget_state_from_profile(data: Mapping[str, Any]) -> None:
    """Synchronise Streamlit widget state from ``data``."""

    for path, value in iter_profile_scalars(data):
        if path in st.session_state:
            continue
        from wizard._logic import _normalize_semantic_empty

        normalized = _normalize_semantic_empty(value)
        if normalized is None:
            st.session_state.pop(path, None)
        else:
            st.session_state[path] = value


def bootstrap_navigation_state(
    *,
    session_state: MutableMapping[str, Any] | Any,
    query_params: MutableMapping[str, Any] | Any,
    wizard_id: str,
    active_step_keys: Sequence[str],
    default_step_key: str,
    legacy_index_to_key: Mapping[int, str],
) -> dict[str, object]:
    """Create or migrate canonical navigation state once per session bootstrap."""

    session_keys = WizardSessionKeys(wizard_id=wizard_id)
    migration_key = session_keys.namespace("legacy_migrated")
    active_keys = set(active_step_keys)

    existing = session_state.get(session_keys.navigation_state)
    if isinstance(existing, Mapping):
        state = dict(existing)
    else:
        state = {}

    if not session_state.get(migration_key):
        legacy = session_state.get("wizard")
        legacy_state = dict(legacy) if isinstance(legacy, Mapping) else {}
        legacy_step = legacy_state.get("current_step")
        if not isinstance(legacy_step, str) or legacy_step not in active_keys:
            legacy_index = session_state.get(StateKeys.STEP)
            if isinstance(legacy_index, bool):
                legacy_index = int(legacy_index)
            if isinstance(legacy_index, int):
                legacy_step = legacy_index_to_key.get(legacy_index)
        if isinstance(legacy_step, str) and legacy_step in active_keys:
            state["current_step"] = legacy_step
        for key in ("history", "completed_steps", "skipped_steps"):
            values = legacy_state.get(key)
            if isinstance(values, list):
                state[key] = [item for item in values if isinstance(item, str) and item in active_keys]
        session_state[migration_key] = True

    current = state.get("current_step")
    if not isinstance(current, str) or current not in active_keys:
        state["current_step"] = default_step_key
    if not isinstance(state.get("history"), list):
        state["history"] = []

    session_state[session_keys.navigation_state] = state
    if wizard_id == "default":
        session_state["wizard"] = state

    step_values: list[str] = []
    if hasattr(query_params, "get_all"):
        raw = query_params.get_all("step")
        if isinstance(raw, list):
            step_values = [item for item in raw if isinstance(item, str)]
    elif isinstance(query_params, Mapping):
        current_query = query_params.get("step")
        if isinstance(current_query, str):
            step_values = [current_query]

    if not step_values:
        query_params["step"] = state["current_step"]
    return state


def get_current_step_key(
    *,
    session_state: Mapping[str, Any] | Any,
    wizard_id: str,
    default_step_key: str,
) -> str:
    """Return the canonical step key from namespaced navigation state."""

    session_keys = WizardSessionKeys(wizard_id=wizard_id)
    state = session_state.get(session_keys.navigation_state)
    if isinstance(state, Mapping):
        current = state.get("current_step")
        if isinstance(current, str) and current:
            return current
    return default_step_key


def set_current_step_key(
    *,
    session_state: MutableMapping[str, Any] | Any,
    query_params: MutableMapping[str, Any] | Any,
    wizard_id: str,
    target_key: str,
) -> None:
    """Persist ``target_key`` in canonical navigation state and query params."""

    session_keys = WizardSessionKeys(wizard_id=wizard_id)
    state = session_state.get(session_keys.navigation_state)
    payload = dict(state) if isinstance(state, Mapping) else {}
    payload["current_step"] = target_key
    session_state[session_keys.navigation_state] = payload
    if wizard_id == "default":
        session_state["wizard"] = payload
    query_params["step"] = target_key


__all__ = [
    "bootstrap_navigation_state",
    "get_current_step_key",
    "iter_profile_scalars",
    "prime_widget_state_from_profile",
    "set_current_step_key",
]
