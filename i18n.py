"""Core translation utilities for Vacalyser."""

from __future__ import annotations

STR = {
    "de": {
        "intro_title": "Identifiziere ALLE recruiting-relevanten Informationen Deiner Vakanz!",
        "source": "Quelle",
        "analyze": "🔎 Automatisch analysieren (LLM)",
        "missing": "Es fehlen noch kritische Felder:",
    },
    "en": {
        "intro_title": "Identify ALL recruiting-relevant information about your profile!",
        "source": "Source",
        "analyze": "🔎 Analyze automatically (LLM)",
        "missing": "Critical fields still missing:",
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
