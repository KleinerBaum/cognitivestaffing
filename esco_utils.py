import requests

# Simple in-memory cache for ESCO lookups to avoid repeated API calls
_esco_cache = {}

def lookup_esco_skill(skill_name: str, lang: str = "en") -> dict:
    """Query the ESCO API for a given skill name and return the top result info."""
    if not skill_name:
        return {}
    key = (skill_name.lower(), lang)
    if key in _esco_cache:
        return _esco_cache[key]
    try:
        # ESCO Search API: search for skills by text
        url = f"https://esco.ec.europa.eu/api/search?type=skill&text={skill_name}&language={lang}&limit=1"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("_embedded", {}).get("results", [])
            if results:
                skill = results[0]  # first result
                # Use preferred label if available
                preferred = skill.get("preferredLabel", {})
                label = preferred.get(lang) or preferred.get("en") or skill_name
                skill_type = skill.get("type", "")
                desc = skill.get("description", {}).get(lang) or ""
                result = {"preferredLabel": label, "type": skill_type, "description": desc}
                _esco_cache[key] = result
                return result
    except Exception as e:
        pass
    # Fallback: return the name itself if no result
    _esco_cache[key] = {}
    return {}

def enrich_skills_with_esco(skill_list: list[str], lang: str = "en") -> list[str]:
    """Replace each skill in the list with ESCO preferred label if available."""
    enriched = []
    for skill in skill_list:
        if not skill:
            continue
        res = lookup_esco_skill(skill, lang=lang)
        if res and res.get("preferredLabel"):
            enriched.append(res["preferredLabel"])
        else:
            enriched.append(skill)
    return enriched
