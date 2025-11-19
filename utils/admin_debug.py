from __future__ import annotations

"""Helpers for gating admin-only debug content in the UI."""

from typing import Final

from typing_shims import streamlit as st

import config as app_config

ADMIN_DEBUG_DETAILS_HINT: Final[tuple[str, str]] = (
    "Technische Details sind nur im Admin-Debug-Panel sichtbar.",
    "Technical details are only visible inside the admin debug panel.",
)


def is_admin_debug_panel_enabled() -> bool:
    """Return ``True`` when the admin debug panel is allowed for this tenant."""

    return bool(app_config.ADMIN_DEBUG_PANEL)


def is_admin_debug_session_active() -> bool:
    """Return ``True`` if the admin debug session flag is active and toggled on."""

    if not is_admin_debug_panel_enabled():
        return False
    try:
        return bool(st.session_state.get("debug"))
    except Exception:  # pragma: no cover - Streamlit session not initialised
        return False
