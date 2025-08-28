from core import esco_utils as esco


def test_classify_occupation(monkeypatch) -> None:
    def fake_get(path, **params):
        if "search" in path:
            return {
                "_embedded": {
                    "results": [
                        {
                            "preferredLabel": {"en": "software developer"},
                            "broaderIscoGroup": ["http://example.com/group"],
                            "uri": "http://example.com/occ",
                        }
                    ]
                }
            }
        return {"title": "Software developers"}

    monkeypatch.setattr(esco, "_get", fake_get)
    res = esco.classify_occupation("Software engineer")
    assert res == {
        "preferredLabel": "software developer",
        "group": "Software developers",
        "uri": "http://example.com/occ",
    }


def test_get_essential_skills(monkeypatch) -> None:
    def fake_get(path, **params):
        return {
            "_links": {
                "hasEssentialSkill": [
                    {"title": "Project management"},
                    {"title": "Python"},
                ]
            }
        }

    monkeypatch.setattr(esco, "_get", fake_get)
    skills = esco.get_essential_skills("http://example.com/occ")
    assert skills == ["Project management", "Python"]


def test_normalize_skills(monkeypatch) -> None:
    def fake_lookup(skill, lang="en"):
        return {"preferredLabel": skill.strip().title()}

    monkeypatch.setattr(esco, "lookup_esco_skill", fake_lookup)
    out = esco.normalize_skills(["python", "Python ", "docker", ""])
    assert out == ["Python", "Docker"]


def test_lookup_esco_skill_caches(monkeypatch) -> None:
    calls = {"count": 0}

    def fake_get(path, **params):
        calls["count"] += 1
        return {"_embedded": {"results": [{"preferredLabel": "Python"}]}}

    esco._SKILL_CACHE.clear()
    monkeypatch.setattr(esco, "_get", fake_get)
    esco.lookup_esco_skill("python")
    esco.lookup_esco_skill("python")
    assert calls["count"] == 1
