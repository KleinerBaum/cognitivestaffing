"""Helpers for interacting with the ESCO taxonomy.

The helpers include lightweight caching and backoff-enabled HTTP
requests for resilience. They provide occupation classification,
essential skill lookup and skill normalization utilities.
"""

from __future__ import annotations

import functools
import logging
import re
from typing import Dict, List, Optional

import backoff
import requests

_ESO = "https://ec.europa.eu/esco/api"
log = logging.getLogger("vacalyser.esco")


def _norm(s: str) -> str:
    """Normalize whitespace and lowercase a string."""

    return re.sub(r"\s+", " ", (s or "")).strip().lower()


@backoff.on_exception(backoff.expo, requests.RequestException, max_time=60)
def _get(path: str, **params) -> dict:
    """Perform a GET request against the ESCO API."""

    url = path if path.startswith("http") else f"{_ESO}/{path.lstrip('/')}"
    resp = requests.get(url, params=params, timeout=20)
    try:  # pragma: no cover - network failures/mocks without method
        resp.raise_for_status()
    except AttributeError:
        pass
    return resp.json()


@functools.lru_cache(maxsize=2048)
def classify_occupation(title: str, lang: str = "en") -> Optional[Dict[str, str]]:
    """Return best matching ESCO occupation for a job title."""

    if not title:
        return None
    data = _get("search", text=title, type="occupation", language=lang)
    items = data.get("_embedded", {}).get("results", []) or []
    if not items and lang != "en":
        return classify_occupation(title, "en")
    if not items:
        return None
    q = _norm(title)

    def _lab(it: dict) -> str:
        lab = it.get("preferredLabel", "")
        if isinstance(lab, dict):
            return lab.get(lang, "") or next(iter(lab.values()), "")
        return str(lab)

    best = max(
        items,
        key=lambda it: (int(q in _norm(_lab(it))) * 2) + int(_norm(_lab(it)) == q),
    )
    group_uri = (best.get("broaderIscoGroup") or [None])[0]
    group = ""
    if group_uri:
        grp = _get(group_uri)
        group = grp.get("title", "")
    return {
        "preferredLabel": _lab(best),
        "uri": best.get("uri") or best.get("_links", {}).get("self", {}).get("href"),
        "group": group,
    }


@functools.lru_cache(maxsize=4096)
def get_essential_skills(occupation_uri: str, lang: str = "en") -> List[str]:
    """Return essential skill labels for a given occupation.

    Args:
        occupation_uri: ESCO URI of the occupation.
        lang: Two-letter language code.

    Returns:
        Alphabetically sorted list of unique skill labels.
    """

    if not occupation_uri:
        return []

    res = _get("resource", uri=occupation_uri, language=lang)
    skills: List[str] = []
    rels = (res.get("_links", {}) or {}).get("hasEssentialSkill", [])
    for rel in rels:
        lab = rel.get("title") or rel.get("preferredLabel") or ""
        if isinstance(lab, dict):
            lab = lab.get(lang, "") or next(iter(lab.values()), "")
        label = str(lab).strip()
        if label:
            skills.append(label)

    return sorted(set(skills))


@functools.lru_cache(maxsize=4096)
def lookup_esco_skill(name: str, lang: str = "en") -> Dict[str, str]:
    """Lookup a skill and return its ESCO metadata."""

    if not name:
        return {}
    data = _get("search", text=name, type="skill", language=lang)
    items = data.get("_embedded", {}).get("results", []) or []
    return items[0] if items else {}


def normalize_skills(skills: List[str], lang: str = "en") -> List[str]:
    """Normalize skill labels using ESCO preferred labels and dedupe."""

    seen: set[str] = set()
    out: List[str] = []
    for skill in skills:
        if not skill:
            continue
        info = lookup_esco_skill(skill, lang=lang)
        label = info.get("preferredLabel") or skill.strip()
        label = label.strip()
        key = label.lower()
        if label and key not in seen:
            seen.add(key)
            out.append(label)
    return out
