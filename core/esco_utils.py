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
_GROUP_CACHE: Dict[Tuple[str | None, str], str] = {}


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


def _preferred_label(item: dict, lang: str) -> str:
    """Return the preferred label of an ESCO item for ``lang``."""

    label = item.get("preferredLabel") or item.get("label") or ""
    if isinstance(label, dict):
        return label.get(lang, "") or next(iter(label.values()), "")
    return str(label)


def _group_label(group_uri: str | None, lang: str) -> str:
    """Resolve the human-readable label of an ISCO group."""

    if not group_uri:
        return ""
    cache_key = (group_uri, lang)
    if cache_key in _GROUP_CACHE:
        return _GROUP_CACHE[cache_key]
    try:
        grp = _get("resource", uri=group_uri, language=lang)
    except requests.RequestException as exc:  # pragma: no cover - network
        log.warning("ESCO group lookup failed: %s", exc)
        return ""
    label = grp.get("title") or grp.get("preferredLabel") or grp.get("label") or ""
    if isinstance(label, dict):
        value = label.get(lang, "") or next(iter(label.values()), "")
    else:
        value = str(label)
    value = value.strip()
    _GROUP_CACHE[cache_key] = value
    return value


def _score_occupation(query_norm: str, item: dict, lang: str) -> float:
    """Compute similarity score between query and occupation label."""

    label = _norm(_preferred_label(item, lang))
    score = SequenceMatcher(None, query_norm, label).ratio()
    if query_norm in label:
        score += 0.1
    if query_norm == label:
        score += 0.1
    return score


def _prepare_occupation_result(item: dict, lang: str) -> Dict[str, str]:
    """Convert an ESCO search item into a compact dict."""

    group_uri = (item.get("broaderIscoGroup") or [None])[0]
    uri = item.get("uri") or item.get("_links", {}).get("self", {}).get("href")
    return {
        "preferredLabel": _preferred_label(item, lang).strip(),
        "uri": uri,
        "group": _group_label(group_uri, lang),
    }


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
    query_norm = _norm(title)
    best = max(items, key=lambda it: _score_occupation(query_norm, it, lang))
    return _prepare_occupation_result(best, lang)


@st.cache_data(show_spinner=False, max_entries=2048)
def search_occupations(
    title: str,
    lang: str = "en",
    limit: int = 5,
) -> List[Dict[str, str]]:
    """Return a ranked list of ESCO occupations for ``title``."""

    if not title:
        return []
    try:
        data = _get("search", text=title, type="occupation", language=lang)
    except requests.RequestException as exc:  # pragma: no cover - network
        log.warning("ESCO occupation search failed: %s", exc)
        return []
    items = data.get("_embedded", {}).get("results", []) or []
    if not items and lang != "en":
        return search_occupations(title, "en", limit=limit)
    if not items:
        return []
    query_norm = _norm(title)
    ranked = sorted(
        items,
        key=lambda it: _score_occupation(query_norm, it, lang),
        reverse=True,
    )
    trimmed = ranked[: max(limit, 1)]
    return [_prepare_occupation_result(item, lang) for item in trimmed]


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
