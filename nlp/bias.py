"""Bias and inclusion language checks."""

from __future__ import annotations

import re
from typing import Dict, List

BIAS_TERMS: Dict[str, Dict[str, str]] = {
    "en": {
        "young": "Specify required experience instead of age.",
        "recent grad": "Use 'entry-level candidate' instead of age-specific terms.",
        "digital native": "Focus on specific technical skills rather than age-related terms.",
        "native speaker": "Specify language proficiency instead of native status.",
        "energetic young team": "Describe team culture without age-related language.",
    },
    "de": {
        "jung": "Beschreiben Sie das notwendige Erfahrungsniveau statt des Alters.",
        "berufsanfänger": "Verwenden Sie 'Einsteiger' oder geben Sie die Erfahrungsebene an.",
        "digital native": "Nennen Sie konkrete digitale Fähigkeiten statt altersbezogener Begriffe.",
        "muttersprachler": "Geben Sie das erforderliche Sprachniveau an statt Muttersprache.",
        "junges, dynamisches team": "Beschreiben Sie die Teamkultur ohne Altersbezug.",
    },
}


def scan_bias_language(text: str, lang: str = "en") -> List[Dict[str, str]]:
    """Scan text for potentially biased terms.

    Args:
        text: Text to analyze.
        lang: Language code (``en`` or ``de``).

    Returns:
        List of findings with the biased ``term`` and an inclusive ``suggestion``.
    """
    text_lower = text.lower()
    mapping = BIAS_TERMS.get(lang[:2], {})
    findings: List[Dict[str, str]] = []
    for term, suggestion in mapping.items():
        pattern = r"\b" + re.escape(term.lower()) + r"\b"
        if re.search(pattern, text_lower):
            findings.append({"term": term, "suggestion": suggestion})
    return findings
