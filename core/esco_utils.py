"""Helpers for interacting with the ESCO taxonomy.

The helpers include lightweight caching and backoff-enabled HTTP
requests for resilience. They provide occupation classification,
essential skill lookup and skill normalization utilities.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, Tuple

from difflib import SequenceMatcher

import backoff
import requests
import streamlit as st

_ESO = "https://ec.europa.eu/esco/api"
_HEADERS = {"User-Agent": "CognitiveNeeds/1.0"}
log = logging.getLogger("cognitive_needs.esco")

_SKILL_CACHE: Dict[Tuple[str, str], Dict[str, str]] = {}


def _norm(s: str) -> str:
    """Normalize whitespace and lowercase a string."""

    return re.sub(r"\s+", " ", (s or "")).strip().lower()


@backoff.on_exception(backoff.expo, requests.RequestException, max_time=60)
def _get(path: str, **params) -> dict:
    """Perform a GET request against the ESCO API."""

    url = path if path.startswith("http") else f"{_ESO}/{path.lstrip('/')}"
    resp = requests.get(url, params=params, timeout=20, headers=_HEADERS)
    try:  # pragma: no cover - network failures/mocks without method
        resp.raise_for_status()
    except AttributeError:
        pass
    return resp.json()


@st.cache_data(show_spinner=False, max_entries=2048)
def classify_occupation(title: str, lang: str = "en") -> Optional[Dict[str, str]]:
    """Return best matching ESCO occupation for a job title."""

    if not title:
        return None
    try:
        data = _get("search", text=title, type="occupation", language=lang)
    except requests.RequestException as exc:  # pragma: no cover - network
        log.warning("ESCO classify failed: %s", exc)
        return None
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

    def _score(it: dict) -> float:
        label = _norm(_lab(it))
        # Base ratio covers partial matches; bonuses favor substring/exact
        score = SequenceMatcher(None, q, label).ratio()
        if q in label:
            score += 0.1
        if q == label:
            score += 0.1
        return score

    best = max(items, key=_score)
    group_uri = (best.get("broaderIscoGroup") or [None])[0]
    group = ""
    if group_uri:
        try:
            grp = _get("resource", uri=group_uri, language=lang)
        except requests.RequestException as exc:  # pragma: no cover - network
            log.warning("ESCO group lookup failed: %s", exc)
        else:
            label = (
                grp.get("title")
                or grp.get("preferredLabel")
                or grp.get("label")
                or ""
            )
            if isinstance(label, dict):
                group = label.get(lang, "") or next(iter(label.values()), "")
            else:
                group = str(label)
            group = group.strip()
    return {
        "preferredLabel": _lab(best),
        "uri": best.get("uri") or best.get("_links", {}).get("self", {}).get("href"),
        "group": group,
    }


@st.cache_data(show_spinner=False, max_entries=4096)
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

    try:
        res = _get("resource", uri=occupation_uri, language=lang)
    except requests.RequestException as exc:  # pragma: no cover - network
        log.warning("ESCO essential skills failed: %s", exc)
        return []
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


def lookup_esco_skill(name: str, lang: str = "en") -> Dict[str, str]:
    """Lookup a skill and return its ESCO metadata.

    Results are cached in-memory to avoid repeated HTTP requests within a
    process. Keys are normalized by lowercasing and collapsing whitespace.
    """

    if not name:
        return {}
    key = (_norm(name), lang)
    if key in _SKILL_CACHE:
        return _SKILL_CACHE[key]
    try:
        data = _get("search", text=name, type="skill", language=lang)
    except requests.RequestException as exc:  # pragma: no cover - network
        log.warning("ESCO lookup failed: %s", exc)
        return {}
    items = data.get("_embedded", {}).get("results", []) or []
    res = items[0] if items else {}
    _SKILL_CACHE[key] = res
    return res


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
