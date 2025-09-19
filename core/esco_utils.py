"""Legacy ESCO helpers now operating in offline-only mode.

All ESCO-related functionality has been disabled. The public helper
functions remain to avoid cascading import errors, but they now return
empty results and perform simple normalization locally without performing
any HTTP requests.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

log = logging.getLogger("cognitive_needs.esco")


def classify_occupation(title: str, lang: str = "en") -> Optional[Dict[str, str]]:
    """Return ``None`` because ESCO classification has been disabled."""

    if title:
        log.info("Skipping ESCO occupation classification for title '%s'", title)
    return None


def search_occupations(
    title: str,
    lang: str = "en",
    limit: int = 5,
) -> List[Dict[str, str]]:
    """Return an empty list because ESCO lookups are disabled."""

    if title:
        log.info("Skipping ESCO occupation search for title '%s'", title)
    return []


def get_essential_skills(occupation_uri: str, lang: str = "en") -> List[str]:
    """Return an empty list because ESCO skill lookup is disabled."""

    if occupation_uri:
        log.info(
            "Skipping ESCO essential skill lookup for occupation '%s'", occupation_uri
        )
    return []


def lookup_esco_skill(name: str, lang: str = "en") -> Dict[str, str]:
    """Return an empty mapping because ESCO skill lookup is disabled."""

    if name:
        log.debug("Skipping ESCO skill lookup for '%s'", name)
    return {}


def normalize_skills(skills: List[str], lang: str = "en") -> List[str]:
    """Normalize skill labels locally without ESCO requests.

    Args:
        skills: Raw skill labels supplied by the user or extraction pipeline.
        lang: Unused language hint retained for backwards compatibility.

    Returns:
        A list of trimmed, case-insensitive unique skill labels.
    """

    deduped: List[str] = []
    seen: set[str] = set()
    for skill in skills:
        label = str(skill or "").strip()
        key = label.casefold()
        if label and key not in seen:
            seen.add(key)
            deduped.append(label)
    return deduped
