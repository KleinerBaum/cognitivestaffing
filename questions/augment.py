"""Augmentation helpers based on ESCO essential skills."""

from __future__ import annotations

from typing import List

from core.esco_utils import get_essential_skills


def missing_esco_skills(
    occupation_code: str,
    hard_skills: List[str],
    tools_and_technologies: List[str],
    lang: str = "en",
) -> List[str]:
    """Return ESCO essential skills not listed in the job description.

    Args:
        occupation_code: ESCO occupation URI.
        hard_skills: Hard skills already provided.
        tools_and_technologies: Tool or technology skills provided.
        lang: Language for ESCO lookup.

    Returns:
        Deterministic list of missing essential skills without duplicates.
    """

    essentials = get_essential_skills(occupation_code, lang=lang)
    existing = {s.lower() for s in hard_skills + tools_and_technologies}
    missing: List[str] = []
    seen: set[str] = set()
    for skill in essentials:
        low = skill.lower()
        if low not in existing and low not in seen:
            seen.add(low)
            missing.append(skill)
    return missing
