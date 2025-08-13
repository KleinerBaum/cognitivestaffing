import openai_utils


def test_generate_interview_guide_includes_culture(monkeypatch):
    captured = {}

    def fake_call_chat_api(messages, **kwargs):
        captured["prompt"] = messages[0]["content"]
        return "guide"

    monkeypatch.setattr(openai_utils, "call_chat_api", fake_call_chat_api)

    openai_utils.generate_interview_guide(
        "Engineer",
        responsibilities="",
        company_culture="Collaborative and transparent",
        tone="casual and friendly",
    )
    prompt = captured["prompt"]
    assert "Company culture: Collaborative and transparent" in prompt
    assert "cultural fit" in prompt.lower()
    assert "Tone: casual and friendly." in prompt


def test_generate_interview_guide_uses_responsibilities(monkeypatch):
    captured = {}

    def fake_call_chat_api(messages, **kwargs):
        captured["prompt"] = messages[0]["content"]
        return "guide"

    monkeypatch.setattr(openai_utils, "call_chat_api", fake_call_chat_api)

    responsibilities = "Design systems\nWrite code"
    openai_utils.generate_interview_guide("Engineer", responsibilities=responsibilities)
    prompt = captured["prompt"]
    assert "Design systems" in prompt
    assert "Write code" in prompt
