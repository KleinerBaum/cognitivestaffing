import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core import suggestions
from core.suggestions import get_benefit_suggestions, get_skill_suggestions
from openai_utils import api as openai_api, extraction


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


def test_suggest_benefits_parses_object_schema(monkeypatch):
    payload = {"items": ["Hybrid work", "Health insurance", "Hybrid work"]}

    monkeypatch.setattr(
        extraction.api,
        "call_chat_api",
        lambda *args, **kwargs: openai_api.ChatCallResult(
            json.dumps(payload),
            [],
            {},
        ),
    )

    result = extraction.suggest_benefits(
        "Engineer",
        existing_benefits="Health insurance",
        model="dummy",
    )

    assert result == ["Hybrid work"]


def test_suggest_benefits_accepts_legacy_list(monkeypatch):
    monkeypatch.setattr(
        extraction.api,
        "call_chat_api",
        lambda *args, **kwargs: openai_api.ChatCallResult(
            json.dumps(["Remote work", "Bonus"]),
            [],
            {},
        ),
    )

    result = extraction.suggest_benefits("Engineer", model="dummy")

    assert result == ["Remote work", "Bonus"]
