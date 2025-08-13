import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.field_suggestions import (
    FIELD_SUGGESTIONS,
    get_field_suggestions,
)  # noqa: E402


def test_get_field_suggestions_normalizes(monkeypatch) -> None:
    def fake_normalize(skills, lang="en"):
        return [s.title() for s in skills]

    monkeypatch.setattr("core.field_suggestions.normalize_skills", fake_normalize)
    out = get_field_suggestions("programming_languages")
    assert out == [s.title() for s in FIELD_SUGGESTIONS["programming_languages"]]


def test_get_field_suggestions_unknown_field() -> None:
    assert get_field_suggestions("unknown") == []
