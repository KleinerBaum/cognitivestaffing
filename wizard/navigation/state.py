"""Utilities for synchronizing Streamlit widget state with profiles."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

import streamlit as st

from wizard._logic import _normalize_semantic_empty


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
        normalized = _normalize_semantic_empty(value)
        if normalized is None:
            st.session_state.pop(path, None)
        else:
            st.session_state[path] = value


__all__ = [
    "iter_profile_scalars",
    "prime_widget_state_from_profile",
]
