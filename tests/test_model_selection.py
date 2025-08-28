import openai_utils
import core.esco_utils as esco_utils
import streamlit as st


def test_suggest_additional_skills_model(monkeypatch):
    captured = {}

    def fake_call_chat_api(messages, model=None, **kwargs):
        captured["model"] = model
        return "- Tech1\n- Tech2\nSoft skills:\n- Communication"

    monkeypatch.setattr(openai_utils, "call_chat_api", fake_call_chat_api)
    monkeypatch.setattr(esco_utils, "normalize_skills", lambda skills, **_: skills)
    out = openai_utils.suggest_additional_skills("Engineer", model="gpt-4")
    assert captured["model"] == "gpt-4"
    assert out["technical"] == ["Tech1", "Tech2"]
    assert out["soft"] == ["Communication"]


def test_suggest_benefits_model(monkeypatch):
    captured = {}

    def fake_call_chat_api(messages, model=None, **kwargs):
        captured["model"] = model
        return "- BenefitA\n- BenefitB"

    monkeypatch.setattr(openai_utils, "call_chat_api", fake_call_chat_api)
    out = openai_utils.suggest_benefits("Engineer", lang="en", model="gpt-4")
    assert captured["model"] == "gpt-4"
    assert out == ["BenefitA", "BenefitB"]


def test_session_state_model_default(monkeypatch):
    captured = {}
    st.session_state.clear()
    st.session_state["model"] = "gpt-4.1-nano"

    def fake_call_chat_api(messages, model=None, **kwargs):
        captured["model"] = model
        return "- BenefitA\n- BenefitB"

    monkeypatch.setattr(openai_utils, "call_chat_api", fake_call_chat_api)
    out = openai_utils.suggest_benefits("Engineer")
    assert captured["model"] == "gpt-4.1-nano"
    assert out == ["BenefitA", "BenefitB"]
