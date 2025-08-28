import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core import suggestions
from core.suggestions import get_benefit_suggestions, get_skill_suggestions


def test_get_skill_suggestions(monkeypatch):
    monkeypatch.setattr(
        suggestions,
        "suggest_skills_for_role",
        lambda title, lang="en": {
            "tools_and_technologies": ["T"],
            "hard_skills": [],
            "soft_skills": [],
        },
    )
    sugg, err = get_skill_suggestions("Engineer")
    assert sugg["tools_and_technologies"] == ["T"]
    assert err is None


def test_get_skill_suggestions_error(monkeypatch):
    def raiser(*args, **kwargs):
        raise RuntimeError("fail")

    monkeypatch.setattr(suggestions, "suggest_skills_for_role", raiser)
    sugg, err = get_skill_suggestions("Engineer")
    assert sugg == {}
    assert err == "fail"


def test_get_benefit_suggestions(monkeypatch):
    monkeypatch.setattr(suggestions, "suggest_benefits", lambda *a, **k: ["A", "B"])
    sugg, err = get_benefit_suggestions("Engineer")
    assert sugg == ["A", "B"]
    assert err is None


def test_get_benefit_suggestions_error(monkeypatch):
    def raiser(*args, **kwargs):
        raise RuntimeError("nope")

    monkeypatch.setattr(suggestions, "suggest_benefits", raiser)
    sugg, err = get_benefit_suggestions("Engineer")
    assert sugg == []
    assert err == "nope"
