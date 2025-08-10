"""Utilities for interacting with the ESCO API."""

from typing import Dict

import requests

_esco_cache: Dict[tuple[str, str], Dict] = {}
_occupation_cache: Dict[tuple[str, str], Dict[str, str]] = {}


def lookup_esco_skill(skill_name: str, lang: str = "en") -> dict:
    if not skill_name:
        return {}
    key = (skill_name.lower(), lang)
    if key in _esco_cache:
        return _esco_cache[key]
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
                result = {
                    "preferredLabel": label,
                    "type": skill.get("type", ""),
                    "description": desc,
                }
                _esco_cache[key] = result
                return result
    except Exception:
        pass
    _esco_cache[key] = {}
    return {}


def enrich_skills_with_esco(skill_list: list[str], lang: str = "en") -> list[str]:
    enriched = []
    for skill in skill_list:
        if not skill:
            continue
        res = lookup_esco_skill(skill, lang=lang)
        enriched.append(res.get("preferredLabel") or skill)
    return enriched


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
        A dictionary containing ``preferredLabel`` and ``group`` keys. Empty
        if no match was found or the API call failed.
    """

    if not job_title:
        return {}
    cache_key = (job_title.lower(), lang)
    if cache_key in _occupation_cache:
        return _occupation_cache[cache_key]
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
                result = {"preferredLabel": label, "group": group_label}
                _occupation_cache[cache_key] = result
                return result
    except Exception:
        pass
    _occupation_cache[cache_key] = {}
    return {}
