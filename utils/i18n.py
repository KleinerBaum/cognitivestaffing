"""Simple i18n helper utilities."""

from __future__ import annotations

import streamlit as st


def tr(de: str, en: str, lang: str | None = None) -> str:
    """Return the string matching the current language.

    Args:
        de: German text.
        en: English text.
        lang: Optional language override (``"de"`` or ``"en"``).

    Returns:
        The localized string for the requested language.
    """
    code = lang or st.session_state.get("lang", "de")
    return de if code == "de" else en
