"""Disabled ESCO integration wrapper."""

from __future__ import annotations

import logging
from typing import Dict, List

log = logging.getLogger("cognitive_needs.esco")


def search_occupation(title: str, lang: str = "en") -> Dict[str, str]:
    """Return an empty mapping because ESCO features are disabled."""

    if title:
        log.info("Skipping ESCO occupation lookup for '%s'", title)
    return {}


def search_occupation_options(
    title: str,
    lang: str = "en",
    limit: int = 5,
) -> List[Dict[str, str]]:
    """Return an empty list of occupation options."""

    if title:
        log.info("Skipping ESCO occupation options lookup for '%s'", title)
    return []


def enrich_skills(occupation_uri: str, lang: str = "en") -> List[str]:
    """Return an empty list because ESCO enrichment is disabled."""

    if occupation_uri:
        log.info("Skipping ESCO skill enrichment for occupation '%s'", occupation_uri)
    return []
