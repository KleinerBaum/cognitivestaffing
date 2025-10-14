"""Tests covering model routing and fallbacks for OpenAI integrations."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Iterator

import pytest
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config
import core.esco_utils as esco_utils
import openai_utils
from openai_utils import ChatCallResult


def test_suggest_additional_skills_model(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str | None] = {}

    def fake_call_chat_api(messages: Any, model: str | None = None, **kwargs: Any) -> ChatCallResult:
        captured["model"] = model
        return ChatCallResult("- Tech1\n- Tech2\nSoft skills:\n- Communication", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)
    monkeypatch.setattr(esco_utils, "normalize_skills", lambda skills, **_: skills)
    out = openai_utils.suggest_additional_skills("Engineer", model="gpt-5-mini")
    assert captured["model"] == "gpt-5-mini"
    assert out["technical"] == ["Tech1", "Tech2"]
    assert out["soft"] == ["Communication"]


def test_suggest_benefits_model(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str | None] = {}

    def fake_call_chat_api(messages: Any, model: str | None = None, **kwargs: Any) -> ChatCallResult:
        captured["model"] = model
        return ChatCallResult("- BenefitA\n- BenefitB", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)
    out = openai_utils.suggest_benefits("Engineer", lang="en", model="gpt-5-nano")
    assert captured["model"] == "gpt-5-nano"
    assert out == ["BenefitA", "BenefitB"]


def test_suggest_benefits_dispatch_default(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str | None] = {}
    st.session_state.clear()

    def fake_call_chat_api(messages: Any, model: str | None = None, **kwargs: Any) -> ChatCallResult:
        captured["model"] = model
        return ChatCallResult("- BenefitA\n- BenefitB", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)
    out = openai_utils.suggest_benefits("Engineer")
    assert captured["model"] == "gpt-5-nano"
    assert out == ["BenefitA", "BenefitB"]


def test_manual_override_reroutes_all_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str | None] = {}
    st.session_state.clear()
    st.session_state["model_override"] = "gpt-5-mini"

    def fake_call_chat_api(messages: Any, model: str | None = None, **kwargs: Any) -> ChatCallResult:
        captured["model"] = model
        return ChatCallResult("- BenefitA\n- BenefitB", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)
    out = openai_utils.suggest_benefits("Engineer")
    assert captured["model"] == "gpt-5-mini"
    assert out == ["BenefitA", "BenefitB"]


def test_legacy_override_aliases_to_current_model(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str | None] = {}
    st.session_state.clear()
    st.session_state["model_override"] = "gpt-4o-mini-2024-07-18"

    def fake_call_chat_api(messages: Any, model: str | None = None, **kwargs: Any) -> ChatCallResult:
        captured["model"] = model
        return ChatCallResult("- BenefitA\n- BenefitB", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)
    out = openai_utils.suggest_benefits("Engineer")
    assert captured["model"] == "gpt-5-nano"
    assert out == ["BenefitA", "BenefitB"]


@pytest.fixture(autouse=True)
def _reset_model_availability() -> Iterator[None]:
    """Ensure availability cache is cleared around each test."""

    try:
        st.session_state.clear()
    except Exception:  # pragma: no cover - Streamlit session may not exist
        pass
    config.clear_unavailable_models()
    yield
    config.clear_unavailable_models()


def test_primary_model_used_when_available() -> None:
    """The configured GPT-5 model should be used when still available."""

    fallback_chain = config.get_model_fallbacks_for(config.ModelTask.EXTRACTION)
    assert fallback_chain, "Expected at least one candidate in the fallback chain"

    selected = config.get_model_for(config.ModelTask.EXTRACTION)
    assert selected == fallback_chain[0]


def test_falls_back_to_gpt4_when_gpt5_missing() -> None:
    """When GPT-5 is unavailable the helper should choose GPT-4."""

    fallback_chain = config.get_model_fallbacks_for(config.ModelTask.EXTRACTION)
    assert len(fallback_chain) >= 2, "Expected a secondary fallback entry"

    config.mark_model_unavailable(fallback_chain[0])
    selected = config.get_model_for(config.ModelTask.EXTRACTION)
    assert selected == fallback_chain[1]


def test_falls_back_to_gpt35_when_gpt5_and_gpt4_missing() -> None:
    """If GPT-5 and GPT-4 fail, the router should pick GPT-3.5."""

    fallback_chain = config.get_model_fallbacks_for(config.ModelTask.EXTRACTION)
    assert len(fallback_chain) >= 3, "Expected a tertiary fallback entry"

    config.mark_model_unavailable(fallback_chain[0])
    config.mark_model_unavailable(fallback_chain[1])

    selected = config.get_model_for(config.ModelTask.EXTRACTION)
    assert selected == fallback_chain[2]


def test_marking_unavailable_is_cleared_on_reload() -> None:
    """Reloading the configuration resets availability decisions."""

    fallback_chain = config.get_model_fallbacks_for(config.ModelTask.EXTRACTION)
    primary = fallback_chain[0]
    config.mark_model_unavailable(primary)
    selected = config.get_model_for(config.ModelTask.EXTRACTION)
    assert selected != primary

    config.clear_unavailable_models()
    importlib.reload(config)
    reloaded_chain = config.get_model_fallbacks_for(config.ModelTask.EXTRACTION)
    assert config.get_model_for(config.ModelTask.EXTRACTION) == reloaded_chain[0]
