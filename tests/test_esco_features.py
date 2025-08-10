import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from esco.classify import classify_occupation  # noqa: E402
from esco.normalize import normalize_skills  # noqa: E402
from questions.augment import missing_esco_skills  # noqa: E402


def test_classify_occupation(monkeypatch):
    """Should return label, code and group from ESCO."""

    def fake_get(url, params=None, timeout=5):
        class Resp:
            status_code = 200

            def __init__(self, data):
                self._data = data

            def json(self):
                return self._data

        if "search" in url:
            data = {
                "_embedded": {
                    "results": [
                        {
                            "preferredLabel": {"en": "software developer"},
                            "broaderIscoGroup": [
                                "http://data.europa.eu/esco/isco/C2512"
                            ],
                            "uri": "http://example.com/occ",
                        }
                    ]
                }
            }
            return Resp(data)
        return Resp({"title": "Software developers"})

    monkeypatch.setattr("esco.classify.requests.get", fake_get)
    res = classify_occupation("Software engineer", "")
    assert res == {
        "occupation_label": "software developer",
        "occupation_code": "http://example.com/occ",
        "group": "Software developers",
    }


def test_normalize_skills(monkeypatch):
    """Skills are normalized to preferred labels and deduped."""

    def fake_lookup(name, lang="en"):
        mapping = {
            "python": {"preferredLabel": "Python"},
            "management": {"preferredLabel": "Project management"},
        }
        return mapping.get(name.lower(), {})

    monkeypatch.setattr("esco.normalize.lookup_esco_skill", fake_lookup)
    out = normalize_skills(["Python", "python", "Management"])
    assert out == ["Python", "Project management"]


def test_missing_esco_skills(monkeypatch):
    """Essential skills not in provided lists are surfaced."""

    def fake_essentials(code, lang="en"):
        return ["Python", "Git", "Python", "Project management"]

    monkeypatch.setattr("questions.augment.get_essential_skills", fake_essentials)
    missing = missing_esco_skills("code", ["python"], ["Docker"])
    assert missing == ["Git", "Project management"]
