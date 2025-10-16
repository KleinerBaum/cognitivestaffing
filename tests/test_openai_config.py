import importlib
import os
import sys
from pathlib import Path

import pytest
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config

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


def test_valid_base_url_us_does_not_set_flag(monkeypatch):
    st.session_state.clear()
    monkeypatch.setattr(config, "OPENAI_API_KEY", "x", raising=False)
    monkeypatch.setattr(es, "OPENAI_API_KEY", "x", raising=False)
    monkeypatch.setattr(config, "OPENAI_BASE_URL", "https://api.openai.com/v1", raising=False)
    monkeypatch.setattr(es, "OPENAI_BASE_URL", "https://api.openai.com/v1", raising=False)

    try:
        es.ensure_state()
        assert st.session_state["openai_base_url_invalid"] is False
    finally:
        st.session_state.clear()


def test_valid_base_url_eu_does_not_set_flag(monkeypatch):
    st.session_state.clear()
    monkeypatch.setattr(config, "OPENAI_API_KEY", "x", raising=False)
    monkeypatch.setattr(es, "OPENAI_API_KEY", "x", raising=False)
    monkeypatch.setattr(config, "OPENAI_BASE_URL", "https://eu.api.openai.com/v1", raising=False)
    monkeypatch.setattr(es, "OPENAI_BASE_URL", "https://eu.api.openai.com/v1", raising=False)

    try:
        es.ensure_state()
        assert st.session_state["openai_base_url_invalid"] is False
    finally:
        st.session_state.clear()


def test_ensure_state_normalises_legacy_models():
    st.session_state.clear()
    st.session_state["model"] = "gpt-4o"
    st.session_state["model_override"] = "gpt-4o-mini"
    es.ensure_state()
    assert st.session_state["model"] == config.GPT4O
    assert st.session_state["model_override"] == config.GPT4O_MINI


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


@pytest.mark.parametrize("model_alias", ["gpt-5-mini", "GPT-5-MINI"])
def test_ensure_state_normalises_openai_model_from_secrets(monkeypatch, model_alias):
    st.session_state.clear()
    monkeypatch.setattr(
        st,
        "secrets",
        {"openai": {"OPENAI_MODEL": model_alias}},
        raising=False,
    )
    monkeypatch.setattr(config, "OPENAI_MODEL", model_alias, raising=False)
    monkeypatch.setattr(es, "OPENAI_MODEL", model_alias, raising=False)

    es.ensure_state()

    assert config.OPENAI_MODEL == config.GPT5_MINI
    assert st.session_state["model"] == config.GPT5_MINI


@pytest.mark.parametrize("env_value", ["", "   "])
def test_default_model_falls_back_to_gpt5_mini_for_blank_env(monkeypatch, env_value):
    previous_env = os.environ.get("DEFAULT_MODEL")

    try:
        monkeypatch.setenv("DEFAULT_MODEL", env_value)
        importlib.reload(config)

        assert config.DEFAULT_MODEL == config.GPT4O
    finally:
        if previous_env is None:
            monkeypatch.delenv("DEFAULT_MODEL", raising=False)
        else:
            monkeypatch.setenv("DEFAULT_MODEL", previous_env)
        importlib.reload(config)


def test_default_model_alias_falls_back_to_gpt5_mini(monkeypatch):
    previous_env = os.environ.get("DEFAULT_MODEL")

    try:
        monkeypatch.setenv("DEFAULT_MODEL", "gpt-5-mini")
        importlib.reload(config)

        assert config.DEFAULT_MODEL == config.GPT5_MINI
    finally:
        if previous_env is None:
            monkeypatch.delenv("DEFAULT_MODEL", raising=False)
        else:
            monkeypatch.setenv("DEFAULT_MODEL", previous_env)
        importlib.reload(config)
