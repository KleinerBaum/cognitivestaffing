"""Shared helpers for maintaining Streamlit widget state."""

from __future__ import annotations

from typing import Any, Callable

import streamlit as st

from ._logic import _update_profile


def _normalize_session_value(value: Any) -> Any:
    """Convert session payloads to serialisable structures."""

    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    return value


def _ensure_widget_state(key: str, value: Any) -> None:
    """Keep ``st.session_state[key]`` synchronised with ``value``."""

    normalized_value = _normalize_session_value(value)
    current = _normalize_session_value(st.session_state.get(key, None))
    if key not in st.session_state or current != normalized_value:
        st.session_state[key] = normalized_value


def _build_on_change(path: str, key: str) -> Callable[[], None]:
    """Return a callback that persists widget updates to the profile."""

    def _callback() -> None:
        value = _normalize_session_value(st.session_state.get(key))
        _update_profile(path, value)

    return _callback


__all__ = ["_ensure_widget_state", "_build_on_change", "_normalize_session_value"]
