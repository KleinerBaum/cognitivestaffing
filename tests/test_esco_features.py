import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.esco_utils import classify_occupation, normalize_skills  # noqa: E402


def test_classify_occupation(monkeypatch):
    """Should return label, code and group from ESCO."""

    def fake_get(url, params=None, timeout=5, headers=None):
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

    monkeypatch.setattr("core.esco_utils.requests.get", fake_get)
    res = classify_occupation("Software engineer")
    assert res == {
        "preferredLabel": "software developer",
        "group": "Software developers",
        "uri": "http://example.com/occ",
    }


def test_normalize_skills(monkeypatch):
    """Skills are normalized to preferred labels and deduped."""

    def fake_lookup(name, lang="en"):
        mapping = {
            "python": {"preferredLabel": "Python"},
            "management": {"preferredLabel": "Project management"},
        }
        return mapping.get(name.lower(), {})

    monkeypatch.setattr("core.esco_utils.lookup_esco_skill", fake_lookup)
    out = normalize_skills(["Python", "python", "Management"])
    assert out == ["Python", "Project management"]
