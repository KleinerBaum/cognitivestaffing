"""ESCO integration wrapper with offline fallbacks."""

import os
from core import esco_utils

OFFLINE = bool(os.getenv("VACAYSER_OFFLINE", False))


def search_occupation(title: str, lang: str = "en") -> dict[str, str]:
    """Search ESCO occupation by title.

    Args:
        title: Job title to classify.
        lang: Two-letter language code.

    Returns:
        Mapping with occupation metadata. Empty if not found.
    """
    if not title:
        return {}
    if OFFLINE:
        # Fallback: simple mapping for common titles (this would be loaded from a local JSON or hardcoded)
        title_key = title.strip().lower()
        data = _OFFLINE_OCCUPATIONS.get(title_key) or {}
        return data
    # Online mode: call actual ESCO API
    return esco_utils.classify_occupation(title, lang) or {}


def enrich_skills(occupation_uri: str, lang: str = "en") -> list[str]:
    """Retrieve essential skills for an occupation.

    Args:
        occupation_uri: ESCO URI of the occupation.
        lang: Two-letter language code.

    Returns:
        List of essential skill labels.
    """
    if not occupation_uri:
        return []
    if OFFLINE:
        return _OFFLINE_SKILLS.get(occupation_uri, [])
    return esco_utils.get_essential_skills(occupation_uri, lang)


# Example offline fixture data (to be replaced with actual data or loaded from file)
_OFFLINE_OCCUPATIONS = {
    "software engineer": {
        "preferredLabel": "Software developers",
        "uri": "http://data.europa.eu/esco/occupation/12345",
        "group": "Information and communications technology professionals",
    }
}
_OFFLINE_SKILLS = {
    "http://data.europa.eu/esco/occupation/12345": [
        "Python",
        "Agile methodologies",
        "Version control",
    ]
}
