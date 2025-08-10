"""Occupation classification via ESCO API."""

from __future__ import annotations

from typing import Dict, Tuple

import requests

# cache: (title, text, lang) -> result
_occ_cache: Dict[Tuple[str, str, str], Dict[str, str]] = {}


def classify_occupation(title: str, text: str, lang: str = "en") -> Dict[str, str]:
    """Return ESCO occupation info for a job title and description text.

    Args:
        title: Job title provided by the user.
        text: Optional description text to improve search context.
        lang: Preferred language for labels.

    Returns:
        Dict with ``occupation_label``, ``occupation_code`` and ``group`` keys.
        Empty dict if nothing was found or the request failed.
    """

    if not title:
        return {}
    cache_key = (title.lower(), (text or "").lower(), lang)
    if cache_key in _occ_cache:
        return _occ_cache[cache_key]

    query = title
    if text:
        query = f"{title} {text}"
    try:
        resp = requests.get(
            "https://ec.europa.eu/esco/api/search",
            params={"type": "occupation", "text": query, "language": lang, "limit": 1},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("_embedded", {}).get("results", [])
            if results:
                occ = results[0]
                label = occ.get("preferredLabel", {}).get(lang) or occ.get("title", "")
                code = occ.get("uri", "")
                group_uri = (occ.get("broaderIscoGroup") or [None])[0]
                group_label = ""
                if group_uri:
                    group_resp = requests.get(
                        "https://ec.europa.eu/esco/api/resource",
                        params={"uri": group_uri, "language": lang},
                        timeout=5,
                    )
                    if group_resp.status_code == 200:
                        group_label = group_resp.json().get("title", "")
                result = {
                    "occupation_label": label,
                    "occupation_code": code,
                    "group": group_label,
                }
                _occ_cache[cache_key] = result
                return result
    except Exception:
        pass
    _occ_cache[cache_key] = {}
    return {}
