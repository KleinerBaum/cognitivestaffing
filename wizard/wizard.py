"""Backwards-compatible exports for profile widget helpers."""

from __future__ import annotations

from components.widget_factory import (
    multiselect as profile_multiselect,
    select as profile_selectbox,
    text_input as profile_text_input,
)

__all__ = [
    "profile_text_input",
    "profile_selectbox",
    "profile_multiselect",
]
