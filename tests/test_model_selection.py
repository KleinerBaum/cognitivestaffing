import openai_utils
import core.esco_utils as esco_utils
import streamlit as st
from openai_utils import ChatCallResult


def test_suggest_additional_skills_model(monkeypatch):
    captured = {}

    def fake_call_chat_api(messages, model=None, **kwargs):
        captured["model"] = model
        return ChatCallResult("- Tech1\n- Tech2\nSoft skills:\n- Communication", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)
    monkeypatch.setattr(esco_utils, "normalize_skills", lambda skills, **_: skills)
    out = openai_utils.suggest_additional_skills("Engineer", model="gpt-5-mini")
    assert captured["model"] == "gpt-5-mini"
    assert out["technical"] == ["Tech1", "Tech2"]
    assert out["soft"] == ["Communication"]


def test_suggest_benefits_model(monkeypatch):
    captured = {}

    def fake_call_chat_api(messages, model=None, **kwargs):
        captured["model"] = model
        return ChatCallResult("- BenefitA\n- BenefitB", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)
    out = openai_utils.suggest_benefits("Engineer", lang="en", model="gpt-5-nano")
    assert captured["model"] == "gpt-5-nano"
    assert out == ["BenefitA", "BenefitB"]


def test_suggest_benefits_dispatch_default(monkeypatch):
    captured = {}
    st.session_state.clear()

    def fake_call_chat_api(messages, model=None, **kwargs):
        captured["model"] = model
        return ChatCallResult("- BenefitA\n- BenefitB", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)
    out = openai_utils.suggest_benefits("Engineer")
    assert captured["model"] == "gpt-5-nano"
    assert out == ["BenefitA", "BenefitB"]


def test_manual_override_reroutes_all_tasks(monkeypatch):
    captured = {}
    st.session_state.clear()
    st.session_state["model_override"] = "gpt-5-mini"

    def fake_call_chat_api(messages, model=None, **kwargs):
        captured["model"] = model
        return ChatCallResult("- BenefitA\n- BenefitB", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)
    out = openai_utils.suggest_benefits("Engineer")
    assert captured["model"] == "gpt-5-mini"
    assert out == ["BenefitA", "BenefitB"]


def test_legacy_override_aliases_to_current_model(monkeypatch):
    captured = {}
    st.session_state.clear()
    st.session_state["model_override"] = "gpt-4o-mini-2024-07-18"

    def fake_call_chat_api(messages, model=None, **kwargs):
        captured["model"] = model
        return ChatCallResult("- BenefitA\n- BenefitB", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)
    out = openai_utils.suggest_benefits("Engineer")
    assert captured["model"] == "gpt-5-nano"
    assert out == ["BenefitA", "BenefitB"]
