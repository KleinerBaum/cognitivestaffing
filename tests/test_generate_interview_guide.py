import openai_utils


def test_generate_interview_guide_includes_culture(monkeypatch):
    captured = {}

    def fake_call_chat_api(messages, **kwargs):
        captured["prompt"] = messages[0]["content"]
        return "guide"

    monkeypatch.setattr(openai_utils, "call_chat_api", fake_call_chat_api)

    openai_utils.generate_interview_guide(
        "Engineer",
        tasks="",
        company_culture="Collaborative and transparent",
    )
    prompt = captured["prompt"]
    assert "Company culture: Collaborative and transparent" in prompt
    assert "cultural fit" in prompt.lower()
