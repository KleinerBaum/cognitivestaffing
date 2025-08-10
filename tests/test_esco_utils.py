import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from esco_utils import classify_occupation  # noqa: E402


def test_classify_occupation(monkeypatch):
    """Classification should return label and group from ESCO."""

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
                        }
                    ]
                }
            }
            return Resp(data)
        data = {"title": "Software developers"}
        return Resp(data)

    monkeypatch.setattr("esco_utils.requests.get", fake_get)
    res = classify_occupation("Software engineer")
    assert res == {
        "preferredLabel": "software developer",
        "group": "Software developers",
    }
