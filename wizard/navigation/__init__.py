"""Navigation helpers for the Streamlit wizard."""

from __future__ import annotations

from wizard.navigation.router import BadRequestError, NavigationController, PageProgressSnapshot
from wizard.navigation.state import iter_profile_scalars, prime_widget_state_from_profile
from wizard.navigation.ui import (
    build_navigation_state,
    inject_navigation_style,
    maybe_scroll_to_top,
    render_navigation,
    render_validation_warnings,
)

__all__ = [
    "BadRequestError",
    "NavigationController",
    "PageProgressSnapshot",
    "build_navigation_state",
    "inject_navigation_style",
    "iter_profile_scalars",
    "maybe_scroll_to_top",
    "prime_widget_state_from_profile",
    "render_navigation",
    "render_validation_warnings",
]
