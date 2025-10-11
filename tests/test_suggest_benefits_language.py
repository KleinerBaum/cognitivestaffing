import openai_utils
from openai_utils import ChatCallResult


def test_suggest_benefits_english(monkeypatch):
    captured = {}

    def fake_call_chat_api(messages, model=None, **kwargs):
        captured["prompt"] = messages[0]["content"]
        return ChatCallResult("- Health insurance\n- Gym membership", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)
    out = openai_utils.suggest_benefits("Engineer", lang="en")
    assert "benefits or perks" in captured["prompt"]
    assert out == ["Health insurance", "Gym membership"]


def test_suggest_benefits_german(monkeypatch):
    captured = {}

    def fake_call_chat_api(messages, model=None, **kwargs):
        captured["prompt"] = messages[0]["content"]
        return ChatCallResult("- Gesundheitsversicherung\n- Firmenwagen", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)
    out = openai_utils.suggest_benefits("Ingenieur", lang="de")
    assert "Vorteile oder Zusatzleistungen" in captured["prompt"]
    assert out == ["Gesundheitsversicherung", "Firmenwagen"]


def test_suggest_benefits_focus_areas(monkeypatch):
    captured = {}

    def fake_call_chat_api(messages, model=None, **kwargs):
        captured["prompt"] = messages[0]["content"]
        return ChatCallResult("[]", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)
    openai_utils.suggest_benefits(
        "Engineer",
        focus_areas=["Health", "Flexibility"],
    )
    assert "Health, Flexibility" in captured["prompt"]
