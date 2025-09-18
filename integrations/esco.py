"""ESCO integration wrapper with offline fallbacks."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, List

from core import esco_utils

log = logging.getLogger("cognitive_needs.esco")

# Environment flag intentionally named ``VACAYSER_OFFLINE`` (without an ``l``)
# to match historical "Vacayser" naming used in earlier deployments.
OFFLINE = bool(os.getenv("VACAYSER_OFFLINE", False))

_OFFLINE_OCCUPATIONS: Dict[str, Dict[str, str]] = {}
_OFFLINE_SKILLS: Dict[str, List[str]] = {}

if OFFLINE:
    data_file = Path(__file__).with_name("esco_offline.json")
    try:
        with data_file.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            _OFFLINE_OCCUPATIONS = {
                k.lower(): v for k, v in data.get("occupations", {}).items()
            }
            _OFFLINE_SKILLS = data.get("skills", {})
    except FileNotFoundError:
        log.warning("Offline ESCO data file missing: %s", data_file)

GENERIC_SKILLS = {"communication"}


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
        title_key = title.strip().lower()
        data = _OFFLINE_OCCUPATIONS.get(title_key) or {}
        if not data:
            log.warning("No offline ESCO match for '%s'", title)
        return data
    # Online mode: call actual ESCO API
    return esco_utils.classify_occupation(title, lang) or {}


def search_occupation_options(
    title: str, lang: str = "en", limit: int = 5
) -> list[dict[str, str]]:
    """Return multiple ESCO occupation candidates for a title."""

    if not title:
        return []
    if OFFLINE:
        title_key = title.strip().lower()
        match = _OFFLINE_OCCUPATIONS.get(title_key)
        return [match] if match else []
    return esco_utils.search_occupations(title, lang=lang, limit=limit) or []


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
        skills = _OFFLINE_SKILLS.get(occupation_uri, [])
        if not skills:
            log.warning("No offline ESCO skills for '%s'", occupation_uri)
    else:
        skills = esco_utils.get_essential_skills(occupation_uri, lang)
    return [s for s in skills if s.lower() not in GENERIC_SKILLS]
