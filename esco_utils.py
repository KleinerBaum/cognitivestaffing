import requests

_esco_cache = {}

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
                result = {"preferredLabel": label, "type": skill.get("type",""), "description": desc}
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
