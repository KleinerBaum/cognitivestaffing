"""Factories for profile-bound wizard widgets (Widget Factory Pattern)."""

from __future__ import annotations

from typing import Any, Callable, Sequence, TypeVar

import streamlit as st

from wizard._logic import get_value, resolve_display_value
from wizard._widget_state import _build_on_change, _ensure_widget_state

T = TypeVar("T")


def _normalize_width_kwarg(kwargs: dict[str, Any]) -> None:
    """Coerce deprecated ``use_container_width`` into the modern ``width`` API."""

    if "use_container_width" not in kwargs:
        return

    use_container_width = kwargs.pop("use_container_width")
    if "width" in kwargs:
        return

    if isinstance(use_container_width, bool):
        kwargs["width"] = "stretch" if use_container_width else "content"
    elif use_container_width:
        kwargs["width"] = "stretch"
    else:
        kwargs["width"] = "content"


def text_input(
    path: str,
    label: str,
    *,
    placeholder: str | None = None,
    key: str | None = None,
    default: Any | None = None,
    value_formatter: Callable[[Any | None], str] | None = None,
    widget_factory: Callable[..., str] | None = None,
    allow_callbacks: bool = True,
    **kwargs: Any,
) -> str:
    """Render a profile-bound text input using the shared widget factory."""

    if "on_change" in kwargs:
        raise ValueError("text_input manages on_change internally")
    if "value" in kwargs:
        raise ValueError("text_input derives value from the profile")

    widget_key = key or path
    display_value = resolve_display_value(
        path,
        default=default,
        formatter=value_formatter,
    )
    _ensure_widget_state(widget_key, display_value)

    factory = widget_factory or st.text_input
    call_kwargs = dict(kwargs)
    _normalize_width_kwarg(call_kwargs)
    if placeholder is not None:
        call_kwargs.setdefault("placeholder", placeholder)
    if allow_callbacks:
        call_kwargs.setdefault("on_change", _build_on_change(path, widget_key))

    return factory(
        label,
        value=display_value,
        key=widget_key,
        **call_kwargs,
    )


def select(
    path: str,
    label: str,
    options: Sequence[T],
    *,
    key: str | None = None,
    default: T | None = None,
    widget_factory: Callable[..., T] | None = None,
    **kwargs: Any,
) -> T:
    """Render a profile-bound select widget using the shared factory."""

    if "on_change" in kwargs:
        raise ValueError("select manages on_change internally")

    widget_key = key or path
    option_list = list(options)
    if not option_list:
        raise ValueError("select requires at least one option")

    requested_index = kwargs.pop("index", None)
    current = get_value(path)
    resolved_index: int
    if current in option_list:
        resolved_index = option_list.index(current)
    elif default in option_list:
        resolved_index = option_list.index(default)
    elif requested_index is not None:
        resolved_index = requested_index
    else:
        resolved_index = 0

    if not 0 <= resolved_index < len(option_list):
        raise IndexError("Resolved select index out of range")

    default_value = option_list[resolved_index]
    _ensure_widget_state(widget_key, default_value)

    call_kwargs = dict(kwargs)
    _normalize_width_kwarg(call_kwargs)

    factory = widget_factory or st.selectbox
    return factory(
        label,
        option_list,
        index=resolved_index,
        key=widget_key,
        on_change=_build_on_change(path, widget_key),
        **call_kwargs,
    )


def multiselect(
    path: str,
    label: str,
    options: Sequence[T],
    *,
    key: str | None = None,
    default: Sequence[T] | None = None,
    widget_factory: Callable[..., Sequence[T]] | None = None,
    **kwargs: Any,
) -> list[T]:
    """Render a profile-bound multiselect widget using the shared factory."""

    if "on_change" in kwargs:
        raise ValueError("multiselect manages on_change internally")

    widget_key = key or path
    option_list = list(options)
    provided_default = kwargs.pop("default", None)

    current = get_value(path)
    if provided_default is not None:
        default_selection = list(provided_default)
    elif default is not None:
        default_selection = list(default)
    elif isinstance(current, (list, tuple, set, frozenset)):
        default_selection = [item for item in current if not option_list or item in option_list]
    elif current is None:
        default_selection = []
    else:
        default_selection = [current] if not option_list or current in option_list else []

    _ensure_widget_state(widget_key, list(default_selection))

    call_kwargs = dict(kwargs)
    _normalize_width_kwarg(call_kwargs)

    factory = widget_factory or st.multiselect
    selection = factory(
        label,
        option_list,
        default=default_selection,
        key=widget_key,
        on_change=_build_on_change(path, widget_key),
        **call_kwargs,
    )
    return list(selection)


__all__ = ["text_input", "select", "multiselect"]
