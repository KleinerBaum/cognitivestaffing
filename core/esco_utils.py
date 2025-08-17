# core/esco_utils.py (NEW)
from __future__ import annotations
import re, logging, functools
from typing import Optional, List, Dict
import httpx, backoff

_ESO = "https://ec.europa.eu/esco/api"
_http = httpx.Client(timeout=20.0)
log = logging.getLogger("vacalyser.esco")

def _norm(s: str) -> str: return re.sub(r"\s+", " ", (s or "")).strip().lower()

@backoff.on_exception(backoff.expo, (httpx.HTTPError,), max_time=60)
def _get(path: str, **params) -> dict:
    r = _http.get(f"{_ESO}/{path.lstrip('/')}", params=params); r.raise_for_status(); return r.json()

@functools.lru_cache(maxsize=2048)
def classify_occupation(title: str, lang: str = "en") -> Optional[Dict[str, str]]:
    if not title: return None
    data = _get("search", text=title, type="occupation", language=lang)
    items = (data.get("_embedded", {}).get("results", []) or [])
    if not items and lang != "en":
        return classify_occupation(title, "en")
    if not items: return None
    q = _norm(title)
    def score(it):
        lab = _norm(it.get("preferredLabel", ""))
        return (int(q in lab) * 2) + (1 if lab.startswith(q) else 0) + (1 if lab == q else 0)
    best = max(items, key=score)
    return {
        "label": best.get("preferredLabel"),
        "uri": best.get("_links", {}).get("self", {}).get("href"),
        "group": best.get("groupingLabel"),
    }

@functools.lru_cache(maxsize=4096)
def get_essential_skills(occupation_uri: str, lang: str = "en") -> List[str]:
    if not occupation_uri: return []
    res = _get("resource", uri=occupation_uri, language=lang)
    skills = []
    for rel in (res.get("_links", {}) or {}).get("hasEssentialSkill", []):
        lab = rel.get("title")
        if lab: skills.append(lab)
    return sorted(set(skills), key=str.lower)
