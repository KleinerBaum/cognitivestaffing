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
        "suggestion_group_llm": "LLM-Vorschläge",
        "suggestion_group_esco_skill": "ESCO Pflicht-Skills • Praxis",
        "suggestion_group_esco_knowledge": "ESCO Pflicht-Skills • Wissen",
        "suggestion_group_esco_competence": "ESCO Pflicht-Skills • Kompetenzen",
        "suggestion_group_esco_tools": "ESCO Pflicht-Skills • Tools & Tech",
        "suggestion_group_esco_certificates": "ESCO Pflicht-Skills • Zertifikate",
        "suggestion_group_esco_missing_skill": "Fehlende ESCO-Skills",
        "suggestion_group_esco_missing_knowledge": "Fehlendes ESCO-Wissen",
        "suggestion_group_esco_missing_competence": "Fehlende ESCO-Kompetenzen",
        "suggestion_group_esco_missing_tools": "Fehlende ESCO-Tools",
        "suggestion_group_esco_missing_certificates": "Fehlende ESCO-Zertifikate",
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
        "suggestion_group_llm": "LLM suggestions",
        "suggestion_group_esco_skill": "ESCO essentials • Practical",
        "suggestion_group_esco_knowledge": "ESCO essentials • Knowledge",
        "suggestion_group_esco_competence": "ESCO essentials • Competence",
        "suggestion_group_esco_tools": "ESCO essentials • Tools & Tech",
        "suggestion_group_esco_certificates": "ESCO essentials • Certificates",
        "suggestion_group_esco_missing_skill": "Outstanding ESCO skills",
        "suggestion_group_esco_missing_knowledge": "Outstanding ESCO knowledge",
        "suggestion_group_esco_missing_competence": "Outstanding ESCO competences",
        "suggestion_group_esco_missing_tools": "Outstanding ESCO tools",
        "suggestion_group_esco_missing_certificates": "Outstanding ESCO certificates",
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
