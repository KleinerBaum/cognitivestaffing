import importlib

import config
import streamlit as st

from constants.keys import StateKeys
from models.need_analysis import NeedAnalysisProfile

es = importlib.import_module("state.ensure_state")


def test_missing_api_key_sets_flag(monkeypatch):
    st.session_state.clear()
    monkeypatch.setattr(config, "OPENAI_API_KEY", "", raising=False)
    monkeypatch.setattr(es, "OPENAI_API_KEY", "", raising=False)
    es.ensure_state()
    assert st.session_state["openai_api_key_missing"] is True


def test_invalid_base_url_sets_flag(monkeypatch):
    st.session_state.clear()
    monkeypatch.setattr(config, "OPENAI_API_KEY", "x", raising=False)
    monkeypatch.setattr(es, "OPENAI_API_KEY", "x", raising=False)
    monkeypatch.setattr(config, "OPENAI_BASE_URL", "not a url", raising=False)
    monkeypatch.setattr(es, "OPENAI_BASE_URL", "not a url", raising=False)
    es.ensure_state()
    assert st.session_state["openai_base_url_invalid"] is True


def test_ensure_state_normalises_legacy_models():
    st.session_state.clear()
    st.session_state["model"] = "gpt-4o"
    st.session_state["model_override"] = "gpt-4o-mini"
    es.ensure_state()
    assert st.session_state["model"] == "gpt-5-mini"
    assert st.session_state["model_override"] == "gpt-5-nano"


def test_ensure_state_preserves_minimal_reasoning_level():
    st.session_state.clear()
    st.session_state["reasoning_effort"] = "minimal"

    es.ensure_state()

    assert st.session_state["reasoning_effort"] == "minimal"


def test_ensure_state_salvages_profile_with_extra_fields():
    st.session_state.clear()
    profile = NeedAnalysisProfile().model_dump()
    profile["company"]["name"] = "ACME GmbH"
    profile["position"]["job_title"] = "Data Scientist"
    profile["requirements"]["hard_skills_required"] = ["Python"]
    profile["date_of_employment_start"] = "2024-11-01"
    profile["unknown_section"] = {"foo": "bar"}
    profile["company"]["invalid_field"] = "ignore me"

    st.session_state[StateKeys.PROFILE] = profile

    es.ensure_state()

    result = st.session_state[StateKeys.PROFILE]
    assert result["company"]["name"] == "ACME GmbH"
    assert result["position"]["job_title"] == "Data Scientist"
    assert result["requirements"]["hard_skills_required"] == ["Python"]
    assert result["meta"]["target_start_date"] == "2024-11-01"
    assert "unknown_section" not in result
    assert "invalid_field" not in result["company"]
