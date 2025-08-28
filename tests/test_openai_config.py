import importlib

import streamlit as st
import config

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
