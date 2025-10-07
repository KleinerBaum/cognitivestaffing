"""Core translation utilities for Cognitive Needs."""

from __future__ import annotations

STR = {
    "de": {
        "intro_title": "Identifiziere ALLE recruiting-relevanten Informationen Deiner Vakanz!",
        "source": "Quelle",
        "analyze": "🔎 Automatisch analysieren (LLM)",
        "missing": "Es fehlen noch kritische Felder:",
        "wizard_equity_toggle": "Mitarbeiterbeteiligung?",
        "wizard_benefits_label": "Leistungen",
        "wizard_home_button": "🏠 Startseite",
        "wizard_donate_button": "❤️ Entwickler unterstützen",
    },
    "en": {
        "intro_title": "Identify ALL recruiting-relevant information about your profile!",
        "source": "Source",
        "analyze": "🔎 Analyze automatically (LLM)",
        "missing": "Critical fields still missing:",
        "wizard_equity_toggle": "Equity?",
        "wizard_benefits_label": "Benefits",
        "wizard_home_button": "🏠 Home",
        "wizard_donate_button": "❤️ Donate to the developer",
    },
}


def t(key: str, lang: str) -> str:
    """Translate ``key`` into the requested ``lang``.

    Args:
        key: Lookup key in the translation dictionary.
        lang: Language code (``"de"`` or ``"en"``).

    Returns:
        The localized string if present, otherwise ``key`` itself.
    """

    return STR.get(lang, {}).get(key, key)
