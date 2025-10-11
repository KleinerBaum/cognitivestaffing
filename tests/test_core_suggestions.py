import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from core import suggestions
from core.suggestions import (
    get_benefit_suggestions,
    get_skill_suggestions,
    get_static_benefit_shortlist,
)
from openai_utils import api as openai_api, extraction


def test_get_skill_suggestions(monkeypatch):
    monkeypatch.setattr(
        suggestions,
        "classify_occupation",
        lambda title, lang="en": {"uri": "http://example.com/occupation", "group": ""},
    )
    monkeypatch.setattr(
        suggestions,
        "get_essential_skills",
        lambda uri, lang="en": ["Python"],
    )
    monkeypatch.setattr(
        suggestions,
        "lookup_esco_skill",
        lambda name, lang="en": {
            "preferredLabel": name.title(),
            "skillType": "http://data.europa.eu/esco/skill-type/skill",
        },
    )
    monkeypatch.setattr(
        suggestions,
        "suggest_skills_for_role",
        lambda title, lang="en", focus_terms=None: {
            "tools_and_technologies": ["T"],
            "hard_skills": ["Go"],
            "soft_skills": [],
            "certificates": ["Azure"],
        },
    )
    sugg, err = get_skill_suggestions("Engineer")
    assert sugg == {
        "hard_skills": {"esco_skill": ["Python"], "llm": ["Go"]},
        "tools_and_technologies": {"llm": ["T"]},
        "certificates": {"llm": ["Azure"]},
    }
    assert err is None


def test_get_skill_suggestions_error(monkeypatch):
    def raiser(*args, **kwargs):
        raise RuntimeError("fail")

    monkeypatch.setattr(
        suggestions,
        "classify_occupation",
        lambda title, lang="en": {"uri": "http://example.com/occupation"},
    )
    monkeypatch.setattr(
        suggestions,
        "get_essential_skills",
        lambda uri, lang="en": ["python"],
    )
    monkeypatch.setattr(
        suggestions,
        "lookup_esco_skill",
        lambda name, lang="en": {
            "preferredLabel": name.upper(),
            "skillType": "http://data.europa.eu/esco/skill-type/skill",
        },
    )
    monkeypatch.setattr(suggestions, "suggest_skills_for_role", raiser)
    sugg, err = get_skill_suggestions("Engineer")
    assert sugg == {"hard_skills": {"esco_skill": ["PYTHON"]}}
    assert err == "fail"


def test_get_benefit_suggestions(monkeypatch):
    monkeypatch.setattr(suggestions, "suggest_benefits", lambda *a, **k: ["A", "B"])
    sugg, err, used_fallback = get_benefit_suggestions("Engineer")
    assert sugg == ["A", "B"]
    assert err is None
    assert used_fallback is False


def test_get_benefit_suggestions_error(monkeypatch):
    def raiser(*args, **kwargs):
        raise RuntimeError("nope")

    monkeypatch.setattr(suggestions, "suggest_benefits", raiser)
    sugg, err, used_fallback = get_benefit_suggestions("Engineer", lang="en")
    assert sugg == get_static_benefit_shortlist(lang="en")
    assert err == "nope"
    assert used_fallback is True


def test_get_benefit_suggestions_empty_response(monkeypatch):
    monkeypatch.setattr(suggestions, "suggest_benefits", lambda *a, **k: [])
    sugg, err, used_fallback = get_benefit_suggestions("Engineer", industry="Tech", lang="en")
    assert sugg == get_static_benefit_shortlist(lang="en", industry="Tech")
    assert err is None
    assert used_fallback is True


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
