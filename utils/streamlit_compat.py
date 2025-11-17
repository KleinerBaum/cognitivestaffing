"""Runtime shims that backport newer Streamlit APIs to older versions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

import inspect
import streamlit as st

_T = TypeVar("_T")


def _wrap_missing_width(widget: Callable[..., _T]) -> Callable[..., _T]:
    """Return a wrapper that silently discards unsupported ``width`` kwargs."""

    def _wrapped(*args: Any, **kwargs: Any) -> _T:
        call_kwargs = dict(kwargs)
        call_kwargs.pop("width", None)
        return widget(*args, **call_kwargs)

    return _wrapped


def _patch_widget(name: str) -> None:
    widget = getattr(st, name, None)
    if widget is None or not callable(widget):  # pragma: no cover - safety guard
        return
    signature = inspect.signature(widget)
    if "width" in signature.parameters:
        return
    setattr(st, name, _wrap_missing_width(widget))


for _widget_name in ("selectbox", "multiselect", "text_input", "text_area", "download_button"):
    _patch_widget(_widget_name)
