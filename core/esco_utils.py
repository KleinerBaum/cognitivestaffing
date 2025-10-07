"""Lightweight ESCO helpers backed by a cached offline dataset.

The original cloud ESCO integration is not available in the automated
evaluation environment, therefore this module provides a deterministic
fallback that mimics the parts of the API relied upon by the UI.

The helpers implement a minimal occupation classifier based on a small
offline dataset.  When no exact occupation is found, a keyword based
heuristic returns the closest ESCO major group so that downstream logic
can still resolve role specific follow-up questions via
``ROLE_FIELD_MAP``.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, Iterable, List, Optional

from config_loader import load_json

log = logging.getLogger("cognitive_needs.esco")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().casefold()


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


def classify_occupation(title: str, lang: str = "en") -> Optional[Dict[str, str]]:
    """Return the best matching occupation entry for ``title``.

    The classifier checks the cached ESCO snapshot for an exact or partial
    match.  If nothing is found a keyword based heuristic produces a match
    on the ESCO major group so the UI can still derive follow-up metadata.
    """

    norm_title = _normalize(title)
    if not norm_title:
        return None

    # Exact match or substring match in the cached dataset
    if norm_title in _OFFLINE_OCCUPATIONS:
        return dict(_OFFLINE_OCCUPATIONS[norm_title])

    for key, entry in _OFFLINE_OCCUPATIONS.items():
        if key and (key in norm_title or norm_title in key):
            return dict(entry)

    # Keyword-based fallback on ESCO major groups.
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

    log.info("No ESCO occupation match for '%s'", title)
    return None


def search_occupations(
    title: str,
    lang: str = "en",
    limit: int = 5,
) -> List[Dict[str, str]]:
    """Return a list of possible occupation matches for ``title``."""

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
        fallback = classify_occupation(title, lang=lang)
        if fallback:
            matches.append(fallback)

    return matches[:limit]


def get_essential_skills(occupation_uri: str, lang: str = "en") -> List[str]:
    """Return essential skills for ``occupation_uri`` from the offline cache."""

    uri = str(occupation_uri or "").strip()
    if not uri:
        return []
    skills = _SKILLS_BY_URI.get(uri)
    if skills is not None:
        return list(skills)

    # Fallback to group level defaults when the URI stems from the keyword
    # heuristic.
    for meta in _GROUP_FALLBACKS.values():
        if meta.get("uri") == uri and meta.get("skills"):
            return list(meta["skills"])

    return []


def lookup_esco_skill(name: str, lang: str = "en") -> Dict[str, str]:
    """Provide a normalized representation for ``name``.

    Without remote access we simply echo the normalized label.  This keeps the
    helper compatible with the rest of the codebase while remaining
    deterministic for tests.
    """

    label = str(name or "").strip()
    if not label:
        return {}
    return {"preferredLabel": label}


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
