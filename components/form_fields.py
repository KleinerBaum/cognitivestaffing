"""Reusable form field helpers for Streamlit widgets."""

from __future__ import annotations

from collections.abc import Callable, MutableMapping
from typing import Any

import streamlit as st

Formatter = Callable[[Any], str]
WidgetFactory = Callable[..., str]

__all__ = ["text_input_with_state"]


def _default_formatter(value: Any) -> str:
    """Return ``value`` normalised as a string."""

    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def text_input_with_state(
    label: str,
    *,
    target: MutableMapping[str, Any] | None = None,
    field: str | None = None,
    value_formatter: Formatter | None = None,
    widget_factory: WidgetFactory | None = None,
    default: Any | None = None,
    state_path: str | None = None,
    **text_input_kwargs: Any,
) -> str:
    """Render a text input and synchronise its value back to ``target``.

    Parameters
    ----------
    label:
        The label rendered next to the input widget.
    target:
        Optional mapping whose ``field`` entry should mirror the widget value.
    field:
        Dictionary key within ``target`` that stores the widget value.
    value_formatter:
        Callable that converts stored values to a string representation. Falls
        back to :func:`str` semantics while normalising ``None`` to ``""``.
    widget_factory:
        Alternative callable used to render the widget. Defaults to
        :func:`streamlit.text_input`, which allows using column-scoped widgets
        by passing ``column.text_input``.
    default:
        Explicit default used when neither ``value`` nor ``target`` contain a
        value. Useful when deriving placeholders from related fields.
    text_input_kwargs:
        Additional keyword arguments forwarded to the underlying
        ``st.text_input`` widget.
    """

    formatter = value_formatter or _default_formatter
    widget_kwargs = {k: v for k, v in text_input_kwargs.items() if v is not None}

    explicit_value = widget_kwargs.pop("value", None)
    resolved_value: Any
    if state_path is not None and state_path in st.session_state:
        resolved_value = st.session_state[state_path]
    elif explicit_value is not None:
        resolved_value = explicit_value
    elif target is not None and field is not None:
        resolved_value = target.get(field)
    elif default is not None:
        resolved_value = default
    else:
        resolved_value = ""

    widget_kwargs["value"] = formatter(resolved_value)
    if state_path and "key" not in widget_kwargs:
        widget_kwargs["key"] = state_path

    factory = widget_factory or st.text_input
    value = factory(label, **widget_kwargs)

    if state_path:
        st.session_state[state_path] = value
    if target is not None and field is not None:
        target[field] = value
    return value
