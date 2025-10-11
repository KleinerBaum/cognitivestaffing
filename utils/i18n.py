"""Simple i18n helper utilities."""

from __future__ import annotations

from typing import Final

import streamlit as st


SKILL_MARKET_SELECT_SKILL_LABEL: Final[tuple[str, str]] = (
    "Skill auswählen",
    "Select skill",
)
SKILL_MARKET_SALARY_METRIC_LABEL: Final[tuple[str, str]] = (
    "Gehaltsimpact",
    "Salary impact",
)
SKILL_MARKET_AVAILABILITY_METRIC_LABEL: Final[tuple[str, str]] = (
    "Talent-Verfügbarkeit",
    "Talent availability",
)
SKILL_MARKET_METRIC_CAPTION: Final[tuple[str, str]] = (
    "{skill}: Gehaltsimpact {salary:+.1f}% · Verfügbarkeit {availability:.0f}/100.",
    "{skill}: Salary impact {salary:+.1f}% · Availability {availability:.0f}/100.",
)
SKILL_MARKET_FALLBACK_CAPTION: Final[tuple[str, str]] = (
    "{skill}: Keine Benchmarks – neutrale Platzhalter (0%, 50/100).",
    "{skill}: No benchmarks – using neutral placeholders (0%, 50/100).",
)


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
