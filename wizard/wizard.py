"""Schema-bound widget helpers for the wizard flow (CS_SCHEMA_PROPAGATE)."""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import Any, Callable, Sequence, TypeVar, cast

import streamlit as st

from ._logic import get_value

T = TypeVar("T")

__all__ = [
    "profile_text_input",
    "profile_selectbox",
    "profile_multiselect",
]


UpdateProfileFn = Callable[[str, Any], None]


@lru_cache(maxsize=1)
def _legacy_update_profile() -> UpdateProfileFn:
    """Return the legacy ``_update_profile`` helper lazily."""

    module = import_module("wizard")
    update = getattr(module, "_update_profile", None)
    if not callable(update):  # pragma: no cover - defensive guard
        raise AttributeError("wizard._update_profile is not available")
    return cast(UpdateProfileFn, update)


def _ensure_widget_state(key: str, value: Any) -> None:
    """Prime ``st.session_state`` with ``value`` when ``key`` is missing."""

    if key not in st.session_state:
        st.session_state[key] = value


def _normalize_session_value(value: Any) -> Any:
    """Convert session values to serialisable structures before storing."""

    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    return value


def _build_on_change(path: str, key: str) -> Callable[[], None]:
    """Return a callback that syncs ``st.session_state`` back to the profile."""

    def _callback() -> None:
        value = _normalize_session_value(st.session_state.get(key))
        _legacy_update_profile()(path, value)

    return _callback


def profile_text_input(
    path: str,
    label: str,
    *,
    key: str | None = None,
    **kwargs: Any,
) -> str:
    """Render a text input bound to ``path`` within the profile."""

    if "on_change" in kwargs:
        raise ValueError("profile_text_input manages on_change internally")
    if "value" in kwargs:
        raise ValueError("profile_text_input derives value from the profile")

    widget_key = key or path
    current = get_value(path)
    display_value = "" if current is None else str(current)
    _ensure_widget_state(widget_key, display_value)

    return st.text_input(
        label,
        value=display_value,
        key=widget_key,
        on_change=_build_on_change(path, widget_key),
        **kwargs,
    )


def profile_selectbox(
    path: str,
    label: str,
    options: Sequence[T],
    *,
    key: str | None = None,
    **kwargs: Any,
) -> T:
    """Render a selectbox bound to ``path`` within the profile."""

    if "on_change" in kwargs:
        raise ValueError("profile_selectbox manages on_change internally")

    widget_key = key or path
    option_list = list(options)
    if not option_list:
        raise ValueError("profile_selectbox requires at least one option")

    requested_index = kwargs.pop("index", None)
    current = get_value(path)
    if current in option_list:
        resolved_index = option_list.index(cast(T, current))
    elif requested_index is not None:
        resolved_index = requested_index
    else:
        resolved_index = 0

    if not 0 <= resolved_index < len(option_list):
        raise IndexError("Resolved selectbox index out of range")

    default_value = option_list[resolved_index]
    _ensure_widget_state(widget_key, default_value)

    return st.selectbox(
        label,
        option_list,
        index=resolved_index,
        key=widget_key,
        on_change=_build_on_change(path, widget_key),
        **kwargs,
    )


def profile_multiselect(
    path: str,
    label: str,
    options: Sequence[T],
    *,
    key: str | None = None,
    **kwargs: Any,
) -> list[T]:
    """Render a multiselect bound to ``path`` within the profile."""

    if "on_change" in kwargs:
        raise ValueError("profile_multiselect manages on_change internally")

    widget_key = key or path
    option_list = list(options)
    provided_default = kwargs.pop("default", None)

    current = get_value(path)
    if provided_default is not None:
        default_selection = list(provided_default)
    elif isinstance(current, (list, tuple, set, frozenset)):
        default_selection = [item for item in current if not option_list or item in option_list]
    elif current is None:
        default_selection = []
    else:
        default_selection = [current] if not option_list or current in option_list else []

    _ensure_widget_state(widget_key, list(default_selection))

    return list(
        st.multiselect(
            label,
            option_list,
            default=default_selection,
            key=widget_key,
            on_change=_build_on_change(path, widget_key),
            **kwargs,
        )
    )
