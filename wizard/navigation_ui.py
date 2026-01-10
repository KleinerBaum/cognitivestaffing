from __future__ import annotations

"""Compatibility shim for wizard navigation UI helpers."""

from wizard.navigation.ui import (
    build_navigation_state,
    inject_navigation_style,
    maybe_scroll_to_top,
    render_navigation,
    render_validation_warnings,
)

__all__ = [
    "build_navigation_state",
    "inject_navigation_style",
    "maybe_scroll_to_top",
    "render_navigation",
    "render_validation_warnings",
]
