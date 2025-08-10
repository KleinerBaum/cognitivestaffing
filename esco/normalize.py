"""Normalize skill names to ESCO preferred labels."""

from __future__ import annotations

from typing import List

from esco_utils import lookup_esco_skill


def normalize_skills(skills: List[str], lang: str = "en") -> List[str]:
    """Return ESCO preferred labels for ``skills``.

    Args:
        skills: Raw skill names.
        lang: Language for ESCO lookup.

    Returns:
        List of normalized skill names without duplicates (case-insensitive).
    """

    normalized: List[str] = []
    seen: set[str] = set()
    for skill in skills:
        if not skill:
            continue
        res = lookup_esco_skill(skill, lang=lang)
        label = res.get("preferredLabel") or skill
        norm = label.strip()
        key = norm.lower()
        if key not in seen:
            seen.add(key)
            normalized.append(norm)
    return normalized
