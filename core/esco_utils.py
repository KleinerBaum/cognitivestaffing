"""Utilities for interacting with the ESCO API."""

from functools import lru_cache
from typing import Dict, List

import requests

__all__ = [
    "lookup_esco_skill",
    "normalize_skills",
    "classify_occupation",
    "get_essential_skills",
]


@lru_cache(maxsize=256)
def lookup_esco_skill(skill_name: str, lang: str = "en") -> dict:
    if not skill_name:
        return {}
    try:
        url = f"https://esco.ec.europa.eu/api/search?type=skill&text={skill_name}&language={lang}&limit=1"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("_embedded", {}).get("results", [])
            if results:
                skill = results[0]
                preferred = skill.get("preferredLabel", {})
                label = preferred.get(lang) or preferred.get("en") or skill_name
                desc = skill.get("description", {}).get(lang) or ""
                return {
                    "preferredLabel": label,
                    "type": skill.get("type", ""),
                    "description": desc,
                }
    except Exception:
        pass
    return {}


def normalize_skills(skills: list[str], lang: str = "en") -> list[str]:
    """Return ESCO preferred labels for ``skills`` without duplicates."""

    normalized: list[str] = []
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


@lru_cache(maxsize=256)
def classify_occupation(job_title: str, lang: str = "en") -> Dict[str, str]:
    """Return the closest ESCO occupation for a job title.

    The function queries the ESCO search API to find the best matching
    occupation for ``job_title``. It also resolves the broader ISCO group to
    provide a general category, which can later be used to tailor
    questionnaire flows.

    Args:
        job_title: Raw job title string provided by the user.
        lang: Preferred language code for labels.

    Returns:
        A dictionary containing ``preferredLabel``, ``group`` and ``uri`` keys.
        Empty if no match was found or the API call failed.
    """

    if not job_title:
        return {}
    try:
        search_url = "https://ec.europa.eu/esco/api/search"
        params = {"type": "occupation", "text": job_title, "language": lang, "limit": 1}
        resp = requests.get(search_url, params=params, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("_embedded", {}).get("results", [])
            if results:
                occ = results[0]
                label = occ.get("preferredLabel", {}).get(lang) or occ.get("title", "")
                uri = occ.get("uri", "")
                group_uri = (occ.get("broaderIscoGroup") or [None])[0]
                group_label = ""
                if group_uri:
                    group_resp = requests.get(
                        "https://ec.europa.eu/esco/api/resource",
                        params={"uri": group_uri},
                        timeout=5,
                    )
                    if group_resp.status_code == 200:
                        group_label = group_resp.json().get("title", "")
                return {"preferredLabel": label, "group": group_label, "uri": uri}
    except Exception:
        pass
    return {}


@lru_cache(maxsize=256)
def get_essential_skills(occupation_uri: str, lang: str = "en") -> List[str]:
    """Fetch essential ESCO skills for a given occupation URI."""

    if not occupation_uri:
        return []
    try:
        resp = requests.get(
            "https://ec.europa.eu/esco/api/resource",
            params={"uri": occupation_uri, "language": lang},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            links = data.get("_links", {})
            skills: List[str] = []
            for item in links.get("hasEssentialSkill", []):
                title = item.get("title", "")
                if title:
                    skills.append(title)
            return skills
    except Exception:
        pass
    return []
