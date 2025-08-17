import openai_utils


def test_suggest_benefits_english(monkeypatch):
    captured = {}

    def fake_call_chat_api(messages, model=None, **kwargs):
        captured["prompt"] = messages[0]["content"]
        return "- Health insurance\n- Gym membership"

    monkeypatch.setattr(openai_utils, "call_chat_api", fake_call_chat_api)
    out = openai_utils.suggest_benefits("Engineer", lang="en")
    assert "benefits or perks" in captured["prompt"]
    assert out == ["Health insurance", "Gym membership"]


def test_suggest_benefits_german(monkeypatch):
    captured = {}

    def fake_call_chat_api(messages, model=None, **kwargs):
        captured["prompt"] = messages[0]["content"]
        return "- Gesundheitsversicherung\n- Firmenwagen"

    monkeypatch.setattr(openai_utils, "call_chat_api", fake_call_chat_api)
    out = openai_utils.suggest_benefits("Ingenieur", lang="de")
    assert "Vorteile oder Zusatzleistungen" in captured["prompt"]
    assert out == ["Gesundheitsversicherung", "Firmenwagen"]
