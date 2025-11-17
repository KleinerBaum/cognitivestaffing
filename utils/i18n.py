"""Simple i18n helper utilities."""

from __future__ import annotations

from typing import Final

import streamlit as st


UI_MULTISELECT_ADD_MORE_HINT: Final[tuple[str, str]] = (
    "Weitere Einträge hinzufügen…",
    "Add more entries…",
)

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
    "{skill}: Keine Auswertung verfügbar – bitte Skills erfassen.",
    "{skill}: No benchmarks available – please add skill data.",
)

EMPLOYMENT_TRAVEL_TOGGLE_HELP: Final[tuple[str, str]] = (
    "Aktivieren, wenn regelmäßige Dienstreisen dazugehören – danach erscheinen Eingaben für Reiseanteil, Regionen und Details.",
    "Turn this on when the role expects regular business travel – additional inputs for travel share, regions, and notes will appear.",
)
EMPLOYMENT_RELOCATION_TOGGLE_HELP: Final[tuple[str, str]] = (
    "Aktivieren, wenn ihr beim Umzug unterstützt – danach könnt ihr Konditionen im Relocation-Feld erläutern.",
    "Turn this on when relocation support is available – a follow-up field lets you outline the package terms.",
)
EMPLOYMENT_VISA_TOGGLE_HELP: Final[tuple[str, str]] = (
    "Aktivieren, wenn ihr Arbeitsvisa oder Aufenthaltstitel sponsort – beschreibt Einschränkungen bitte in den Notizen.",
    "Enable this when you sponsor work visas or residency permits – call out any limits in the notes or benefits section.",
)
EMPLOYMENT_OVERTIME_TOGGLE_HELP: Final[tuple[str, str]] = (
    "Aktivieren, wenn Überstunden vertraglich erwartet werden – skizziert das Vergütungs- oder Ausgleichsmodell im Prozess-/Vergütungsblock.",
    "Use this when overtime is contractually expected – describe how it is compensated or offset in the process/compensation notes.",
)
EMPLOYMENT_SECURITY_TOGGLE_HELP: Final[tuple[str, str]] = (
    "Aktivieren, wenn eine Sicherheitsüberprüfung Pflicht ist – nennt die benötigte Stufe in den Anforderungen oder Hinweisen.",
    "Enable this when a security clearance is mandatory – specify the required level in the requirements or additional notes.",
)
EMPLOYMENT_SHIFT_TOGGLE_HELP: Final[tuple[str, str]] = (
    "Aktivieren, wenn Schichtdienst oder Rotationen vorgesehen sind – beschreibt den Rhythmus im Arbeitszeittext.",
    "Turn this on when the role runs on shifts or rotations – outline the cadence in the work schedule details.",
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
