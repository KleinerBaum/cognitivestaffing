"""High level helpers for interacting with the public ESCO API.

The production app talks to the official `ec.europa.eu` ESCO endpoints to
classify occupations and retrieve the associated essential skills.  The
automated evaluation environment does not guarantee outbound connectivity
though, therefore all helpers transparently fall back to a cached offline
dataset when ``VACAYSER_OFFLINE`` is set or when network requests fail.

The module exposes a very small surface that mirrors the behaviour of the
previous stub implementation while adding proper HTTP calls, timeouts and
structured error handling.  Consumers only need to handle ``None`` / empty
results – all exceptions are swallowed locally after logging.
"""

from __future__ import annotations

import json
import logging
import os
import re
from functools import lru_cache
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

import requests

from config_loader import load_json

try:  # pragma: no cover - optional Streamlit caching
    import streamlit as st
except Exception:  # pragma: no cover - Streamlit not available in some envs
    st = None

log = logging.getLogger("cognitive_needs.esco")

REQUEST_TIMEOUT = 6  # seconds
_ESCO_API_ROOT = "https://ec.europa.eu/esco/api"
_SEARCH_URL = f"{_ESCO_API_ROOT}/search"
_OCCUPATION_URL = f"{_ESCO_API_ROOT}/resource/occupation"


class EscoServiceError(RuntimeError):
    """Raised when the ESCO API cannot be reached."""


_SESSION = requests.Session()
_SESSION.headers.update({"Accept": "application/json"})


def _cache_esco_data(*, maxsize: int) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if st is not None:
            cached_func = st.cache_data(show_spinner=False, ttl=3600)(func)
            if not hasattr(cached_func, "cache_clear"):
                cached_func.cache_clear = cached_func.clear  # type: ignore[attr-defined]
            return cached_func
        return lru_cache(maxsize=maxsize)(func)

    return decorator


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().casefold()


def _normalize_lang(lang: str) -> str:
    lang_norm = str(lang or "en").strip().lower()
    if lang_norm.startswith("de"):
        return "de"
    if len(lang_norm) == 2:
        return lang_norm
    return "en"


def _is_offline() -> bool:
    value = str(os.getenv("VACAYSER_OFFLINE", "")).strip().lower()
    return value not in {"", "0", "false", "no"}


def _fetch_json(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a GET request and return the parsed JSON payload."""

    try:
        response = _SESSION.get(url, params=params, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise EscoServiceError(str(exc)) from exc

    try:
        return response.json()
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise EscoServiceError("Invalid JSON from ESCO API") from exc


def _load_offline_data() -> Dict[str, Dict[str, List[str]]]:
    fallback: Dict[str, Dict[str, List[str]]] = {
        "occupations": {},
        "skills": {},
    }
    data = load_json("integrations/esco_offline.json", fallback=fallback)
    if not isinstance(data, dict):  # pragma: no cover - defensive
        return fallback
    occupations = data.get("occupations", {})
    skills = data.get("skills", {})
    if not isinstance(occupations, dict):  # pragma: no cover - defensive
        occupations = {}
    if not isinstance(skills, dict):  # pragma: no cover - defensive
        skills = {}
    return {"occupations": occupations, "skills": skills}


_OFFLINE_DATA = _load_offline_data()

_OFFLINE_OCCUPATIONS: Dict[str, Dict[str, str]] = {}
_SKILLS_BY_URI: Dict[str, List[str]] = {}
_GROUP_FALLBACKS: Dict[str, Dict[str, str]] = {}

for raw_key, payload in _OFFLINE_DATA.get("occupations", {}).items():
    if not isinstance(payload, dict):
        continue
    norm_key = _normalize(raw_key)
    preferred = str(payload.get("preferredLabel") or raw_key).strip()
    uri = str(payload.get("uri") or f"offline://{norm_key.replace(' ', '_')}")
    group = str(payload.get("group") or "").strip()
    entry = {"preferredLabel": preferred, "uri": uri, "group": group}
    _OFFLINE_OCCUPATIONS[norm_key] = entry
    if group:
        group_key = group.casefold()
        meta = _GROUP_FALLBACKS.setdefault(
            group_key,
            {
                "preferredLabel": preferred,
                "uri": uri,
                "group": group,
            },
        )
        if not meta.get("preferredLabel"):
            meta["preferredLabel"] = preferred
        if not meta.get("uri"):
            meta["uri"] = uri

for uri, skills in _OFFLINE_DATA.get("skills", {}).items():
    if not isinstance(skills, Iterable):
        continue
    clean_skills: List[str] = []
    for skill in skills:
        label = str(skill or "").strip()
        if label:
            clean_skills.append(label)
    if clean_skills:
        _SKILLS_BY_URI[uri] = clean_skills

for entry in _OFFLINE_OCCUPATIONS.values():
    group = entry.get("group", "")
    uri = entry.get("uri", "")
    if not group or not uri:
        continue
    skills = _SKILLS_BY_URI.get(uri, [])
    if skills:
        group_key = group.casefold()
        group_meta = _GROUP_FALLBACKS.setdefault(
            group_key,
            {
                "preferredLabel": entry.get("preferredLabel", group.title()),
                "uri": uri,
                "group": group,
            },
        )
        existing = group_meta.setdefault("skills", [])
        for skill in skills:
            if skill not in existing:
                existing.append(skill)


_GROUP_KEYWORDS: Dict[str, List[str]] = {
    "information and communications technology professionals": [
        "developer",
        "software",
        "engineer",
        "programmer",
        "it",
        "data scientist",
        "devops",
        "backend",
        "fullstack",
        "frontend",
    ],
    "sales, marketing and public relations professionals": [
        "sales",
        "account executive",
        "business development",
        "marketing",
        "growth",
        "public relations",
        "communications",
    ],
    "health professionals": [
        "nurse",
        "doctor",
        "physician",
        "medical",
        "surgeon",
        "clinician",
    ],
}


def _offline_classify(title: str) -> Optional[Dict[str, str]]:
    norm_title = _normalize(title)
    if not norm_title:
        return None

    if norm_title in _OFFLINE_OCCUPATIONS:
        return dict(_OFFLINE_OCCUPATIONS[norm_title])

    for key, entry in _OFFLINE_OCCUPATIONS.items():
        if key and (key in norm_title or norm_title in key):
            return dict(entry)

    for group, keywords in _GROUP_KEYWORDS.items():
        for kw in keywords:
            if kw in norm_title:
                meta = _GROUP_FALLBACKS.get(group.casefold())
                if not meta:
                    meta = {
                        "preferredLabel": group.title(),
                        "uri": f"offline://{group.casefold().replace(' ', '_')}",
                        "group": group,
                    }
                    _GROUP_FALLBACKS[group.casefold()] = meta
                if meta["uri"] not in _SKILLS_BY_URI:
                    skills = meta.get("skills", [])
                    if skills:
                        _SKILLS_BY_URI[meta["uri"]] = list(skills)
                return dict(meta)

    return None


def _offline_search(title: str, limit: int) -> List[Dict[str, str]]:
    norm_title = _normalize(title)
    if not norm_title:
        return []

    matches: List[Dict[str, str]] = []
    for key, entry in _OFFLINE_OCCUPATIONS.items():
        if key and (key in norm_title or norm_title in key):
            matches.append(dict(entry))
        if len(matches) >= limit:
            break

    if not matches:
        fallback = _offline_classify(title)
        if fallback:
            matches.append(fallback)

    return matches[:limit]


def _offline_essential_skills(uri: str) -> List[str]:
    skills = _SKILLS_BY_URI.get(uri)
    if skills is not None:
        return list(skills)

    for meta in _GROUP_FALLBACKS.values():
        if meta.get("uri") == uri and meta.get("skills"):
            return list(meta["skills"])

    return []


def get_group_skills(group: str) -> List[str]:
    """Return cached offline skills for an ESCO group when available."""

    key = str(group or "").strip().casefold()
    if not key:
        return []
    meta = _GROUP_FALLBACKS.get(key)
    if not meta:
        return []
    skills = meta.get("skills")
    if not isinstance(skills, Iterable):
        return []
    cleaned: List[str] = []
    for skill in skills:
        label = str(skill or "").strip()
        if label:
            cleaned.append(label)
    return cleaned


def _select_label(preferred: Any, fallback: str, lang: str) -> str:
    if isinstance(preferred, dict):
        lang_norm = _normalize_lang(lang)
        value = preferred.get(lang_norm) or preferred.get("en")
        if value:
            return str(value).strip()
        for candidate in preferred.values():
            if candidate:
                return str(candidate).strip()
    if preferred:
        return str(preferred).strip()
    return str(fallback or "").strip()


def _extract_group(ancestors: Sequence[Dict[str, Any]]) -> str:
    titles: List[str] = []
    for ancestor in ancestors or []:
        title = str(ancestor.get("title") or "").strip()
        if title:
            titles.append(title)

    # Prefer explicitly known offline groups to keep compatibility.
    for title in titles:
        if title.casefold() in _GROUP_FALLBACKS:
            return title

    for title in reversed(titles):
        lowered = title.casefold()
        if any(keyword in lowered for keyword in ("professionals", "managers")):
            return title

    if len(titles) >= 2:
        return titles[-2]
    return titles[-1] if titles else ""


@_cache_esco_data(maxsize=128)
def _get_occupation_detail(uri: str, lang: str) -> Dict[str, Any]:
    params = {"uri": uri, "language": _normalize_lang(lang), "view": "full"}
    return _fetch_json(_OCCUPATION_URL, params)


def _api_search_occupations(title: str, lang: str, limit: int) -> List[Dict[str, str]]:
    params = {
        "text": title,
        "type": "occupation",
        "language": _normalize_lang(lang),
        "limit": max(1, min(limit, 20)),
    }
    payload = _fetch_json(_SEARCH_URL, params)
    results = payload.get("_embedded", {}).get("results", [])
    matches: List[Dict[str, str]] = []
    for result in results:
        uri = str(result.get("uri") or "").strip()
        if not uri:
            continue
        label = _select_label(result.get("preferredLabel"), result.get("title"), lang)
        group = ""
        try:
            detail = _get_occupation_detail(uri, lang)
        except EscoServiceError as exc:
            log.debug("ESCO detail lookup failed for %s: %s", uri, exc)
            detail = {}
        if detail:
            ancestors = detail.get("_embedded", {}).get("ancestors", [])
            group = _extract_group(ancestors)
        matches.append({"preferredLabel": label, "uri": uri, "group": group})
    return matches[:limit]


def classify_occupation(title: str, lang: str = "en") -> Optional[Dict[str, str]]:
    """Return the best matching occupation entry for ``title``."""

    if not str(title or "").strip():
        return None

    offline_match = _offline_classify(title)

    if _is_offline():
        if offline_match:
            return offline_match
        log.info("No offline ESCO occupation match for '%s'", title)
        return None

    try:
        matches = _api_search_occupations(title, lang=lang, limit=1)
    except EscoServiceError as exc:
        log.warning("ESCO occupation search failed (%s); falling back to cache", exc)
        return offline_match

    if matches:
        result = matches[0]
        if offline_match:
            api_group = str(result.get("group") or "").strip().casefold()
            offline_group = str(offline_match.get("group") or "").strip().casefold()
            if offline_group and offline_group != api_group:
                return offline_match
        return result

    return offline_match


def search_occupations(
    title: str,
    lang: str = "en",
    limit: int = 5,
) -> List[Dict[str, str]]:
    """Return a list of possible occupation matches for ``title``."""

    if not str(title or "").strip():
        return []

    if _is_offline():
        return _offline_search(title, limit)

    try:
        matches = _api_search_occupations(title, lang=lang, limit=limit)
    except EscoServiceError as exc:
        log.warning("ESCO occupation search failed (%s); using offline cache", exc)
        return _offline_search(title, limit)

    if matches:
        return matches

    return _offline_search(title, limit)


def _api_essential_skills(uri: str, lang: str) -> List[str]:
    detail = _get_occupation_detail(uri, lang)
    skills: List[str] = []
    for entry in detail.get("_links", {}).get("hasEssentialSkill", []) or []:
        label = str(entry.get("title") or "").strip()
        if label and label not in skills:
            skills.append(label)
    return skills


def get_essential_skills(occupation_uri: str, lang: str = "en") -> List[str]:
    """Return essential skills for ``occupation_uri``."""

    uri = str(occupation_uri or "").strip()
    if not uri:
        return []

    if uri in _SKILLS_BY_URI:
        return _offline_essential_skills(uri)

    if _is_offline() or uri.startswith("offline://"):
        return _offline_essential_skills(uri)

    try:
        skills = _api_essential_skills(uri, lang)
    except EscoServiceError as exc:
        log.warning("ESCO essential skill lookup failed (%s); falling back to cache", exc)
        return _offline_essential_skills(uri)

    if skills:
        return skills

    return _offline_essential_skills(uri)


@_cache_esco_data(maxsize=256)
def _api_lookup_skill(name: str, lang: str) -> Dict[str, str]:
    params = {
        "text": name,
        "type": "skill",
        "language": _normalize_lang(lang),
        "limit": 1,
    }
    payload = _fetch_json(_SEARCH_URL, params)
    results = payload.get("_embedded", {}).get("results", [])
    if not results:
        return {}
    result = results[0]
    label = _select_label(result.get("preferredLabel"), result.get("title"), lang)
    data: Dict[str, str] = {"preferredLabel": label}
    uri = str(result.get("uri") or "").strip()
    if uri:
        data["uri"] = uri
    types = result.get("hasSkillType") or []
    if isinstance(types, list) and types:
        data["skillType"] = str(types[0])
    return data


def lookup_esco_skill(name: str, lang: str = "en") -> Dict[str, str]:
    """Return metadata for ``name`` from ESCO when available."""

    label = str(name or "").strip()
    if not label:
        return {}

    if _is_offline():
        return {"preferredLabel": label}

    try:
        data = _api_lookup_skill(label, lang)
    except EscoServiceError as exc:
        log.warning("ESCO skill lookup failed (%s); returning local normalization", exc)
        return {"preferredLabel": label}

    if not data:
        return {"preferredLabel": label}

    return data


def _friendly_skill_label(original: str, preferred: str) -> str:
    """Return a human-friendly label for a skill.

    The ESCO API often returns verbose entries such as
    ``"Python (computer programming)"``. For display and matching purposes we
    prefer compact variants while keeping the canonical casing when helpful.
    """

    original_clean = str(original or "").strip()
    preferred_clean = str(preferred or "").strip()
    if not preferred_clean:
        return original_clean

    display = preferred_clean
    if "(" in preferred_clean and ")" in preferred_clean:
        head = preferred_clean.split("(", 1)[0].strip()
        if head:
            display = head

    if original_clean:
        if display.casefold() == original_clean.casefold():
            if original_clean.islower() or original_clean.isupper():
                return display
            return original_clean
        preferred_cf = preferred_clean.casefold()
        original_cf = original_clean.casefold()
        if preferred_cf.startswith(original_cf):
            return original_clean
        if original_cf.startswith(preferred_cf):
            return original_clean
        return original_clean

    return display


def normalize_skills(skills: List[str], lang: str = "en") -> List[str]:
    """Normalize skill labels via ESCO when possible."""

    deduped: List[str] = []
    seen: set[str] = set()
    for skill in skills:
        raw_label = str(skill or "").strip()
        if not raw_label:
            continue
        meta = lookup_esco_skill(raw_label, lang=lang)
        preferred_label = str(meta.get("preferredLabel") or raw_label).strip()
        display_label = _friendly_skill_label(raw_label, preferred_label)
        key = (display_label or preferred_label).casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(display_label or preferred_label)
    return deduped
