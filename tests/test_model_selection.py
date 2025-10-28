"""Tests covering model routing and fallbacks for OpenAI integrations."""

from __future__ import annotations

import importlib
import json
import sys
import types
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
from openai import BadRequestError
from components import model_selector as model_selector_component


def test_suggest_skills_for_role_model(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str | None] = {}

    payload = {
        "tools_and_technologies": ["Tool A", "Tool A", "Tool B"],
        "hard_skills": ["Hard Skill 1", ""],
        "soft_skills": ["Soft Skill 1"],
        "certificates": ["Certificate 1"],
    }

    def fake_call_chat_api(messages: Any, model: str | None = None, **kwargs: Any) -> ChatCallResult:
        captured["model"] = model
        return ChatCallResult(json.dumps(payload), [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)
    monkeypatch.setattr(esco_utils, "normalize_skills", lambda skills, **_: skills)
    result = openai_utils.suggest_skills_for_role("Engineer", model=config.GPT5_MINI)

    assert captured["model"] == config.GPT5_MINI
    assert result["tools_and_technologies"] == ["Tool A", "Tool B"]
    assert result["hard_skills"] == ["Hard Skill 1"]
    assert result["soft_skills"] == ["Soft Skill 1"]
    assert result["certificates"] == ["Certificate 1"]


def test_suggest_responsibilities_for_role_model(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str | None] = {}

    payload = {"responsibilities": ["Define roadmap"]}

    def fake_call_chat_api(messages: Any, model: str | None = None, **kwargs: Any) -> ChatCallResult:
        captured["model"] = model
        return ChatCallResult(json.dumps(payload), [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)
    result = openai_utils.suggest_responsibilities_for_role(
        "Product Manager",
        model=config.GPT5_MINI,
        company_name="Acme",
    )

    assert captured["model"] == config.GPT5_MINI
    assert result == ["Define roadmap"]


def test_suggest_benefits_model(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str | None] = {}

    def fake_call_chat_api(messages: Any, model: str | None = None, **kwargs: Any) -> ChatCallResult:
        captured["model"] = model
        return ChatCallResult("- BenefitA\n- BenefitB", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)
    out = openai_utils.suggest_benefits("Engineer", lang="en", model=config.GPT4O_MINI)
    assert captured["model"] == config.GPT4O_MINI
    assert out == ["BenefitA", "BenefitB"]


def test_suggest_benefits_dispatch_default(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str | None] = {}
    st.session_state.clear()

    def fake_call_chat_api(messages: Any, model: str | None = None, **kwargs: Any) -> ChatCallResult:
        captured["model"] = model
        return ChatCallResult("- BenefitA\n- BenefitB", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)
    out = openai_utils.suggest_benefits("Engineer")
    assert captured["model"] == config.GPT5_NANO
    assert out == ["BenefitA", "BenefitB"]


def test_manual_override_reroutes_all_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str | None] = {}
    st.session_state.clear()
    st.session_state["model_override"] = config.GPT5_MINI

    def fake_call_chat_api(messages: Any, model: str | None = None, **kwargs: Any) -> ChatCallResult:
        captured["model"] = model
        return ChatCallResult("- BenefitA\n- BenefitB", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)
    out = openai_utils.suggest_benefits("Engineer")
    assert captured["model"] == config.GPT5_MINI
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
    assert captured["model"] == config.GPT4O_MINI
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


def test_falls_back_to_gpt35_when_gpt4o_missing() -> None:
    """When GPT-4o is unavailable the helper should choose GPT-3.5."""

    fallback_chain = config.get_model_fallbacks_for(config.ModelTask.EXTRACTION)
    assert len(fallback_chain) >= 2, "Expected a secondary fallback entry"

    config.mark_model_unavailable(fallback_chain[0])
    selected = config.get_model_for(config.ModelTask.EXTRACTION)
    assert selected == fallback_chain[1]


def test_falls_back_to_last_candidate_when_all_marked() -> None:
    """If every candidate is unavailable the router still returns the last option."""

    fallback_chain = config.get_model_fallbacks_for(config.ModelTask.EXTRACTION)
    assert fallback_chain, "Expected at least one candidate"

    for candidate in fallback_chain:
        config.mark_model_unavailable(candidate)

    selected = config.get_model_for(config.ModelTask.EXTRACTION)
    assert selected == fallback_chain[-1]


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


def test_call_chat_api_switches_to_fallback_on_unavailable(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """call_chat_api should retry with the next fallback when the primary fails."""

    st.session_state.clear()
    caplog.set_level("WARNING", logger="cognitive_needs.openai")

    attempts: list[str] = []

    def _fake_create_response(payload: dict[str, Any]) -> Any:
        model = payload.get("model")
        attempts.append(str(model))
        if len(attempts) == 1:
            fake_response = types.SimpleNamespace(
                request=types.SimpleNamespace(
                    method="POST",
                    url="https://api.openai.com/v1/responses",
                ),
                status_code=503,
                headers={},
            )
            raise BadRequestError(
                message="The model gpt-4o-mini is currently overloaded.",
                response=fake_response,
                body=None,
            )
        return types.SimpleNamespace(
            output_text="OK",
            output=[],
            usage={"input_tokens": 2, "output_tokens": 3},
            id="resp-final",
        )

    monkeypatch.setattr(openai_utils.api, "_create_response_with_timeout", _fake_create_response)

    result = openai_utils.api.call_chat_api(
        messages=[{"role": "user", "content": "hi"}],
        task=config.ModelTask.EXTRACTION,
    )

    assert result.content == "OK"
    assert attempts[0] == config.GPT4O_MINI
    assert attempts[1] == config.GPT4O
    assert any("retrying with fallback" in record.message for record in caplog.records)


def test_model_selector_uses_translations(monkeypatch: pytest.MonkeyPatch) -> None:
    """The model selector should surface localized labels and auto mode by default."""

    st.session_state.clear()
    st.session_state["lang"] = "de"

    captured: dict[str, object] = {}

    def fake_selectbox(label, options, index=0, key=None, **kwargs):  # type: ignore[no-untyped-def]
        captured["label"] = label
        captured["options"] = list(options)
        captured["index"] = index
        choice = options[index]
        if key is not None:
            st.session_state[key] = choice
        return choice

    monkeypatch.setattr(st, "selectbox", fake_selectbox)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)

    resolved = model_selector_component.model_selector()

    assert captured["label"] == "Basismodell"
    assert any("Automatisch" in option for option in captured["options"])
    assert captured["index"] == 0
    assert resolved == config.OPENAI_MODEL
    assert st.session_state["model_override"] == ""
    assert st.session_state["model"] == config.OPENAI_MODEL


def test_model_selector_updates_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Selecting a manual override stores the normalized value in session state."""

    st.session_state.clear()
    st.session_state["lang"] = "en"

    captured: dict[str, object] = {}

    def fake_selectbox(label, options, index=0, key=None, **kwargs):  # type: ignore[no-untyped-def]
        captured["index"] = index
        choice = options[4]
        if key is not None:
            st.session_state[key] = choice
        return choice

    monkeypatch.setattr(st, "selectbox", fake_selectbox)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)

    resolved = model_selector_component.model_selector()

    assert captured["index"] == 0
    assert resolved == config.GPT5_NANO
    assert st.session_state["model_override"] == config.GPT5_NANO
    assert st.session_state["model"] == config.GPT5_NANO


def test_model_selector_normalises_existing_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing overrides should be normalised and reflected in the default index."""

    st.session_state.clear()
    st.session_state["lang"] = "en"
    st.session_state["model_override"] = "  GPT-5-NANO  "

    captured: dict[str, object] = {}

    def fake_selectbox(label, options, index=0, key=None, **kwargs):  # type: ignore[no-untyped-def]
        captured["index"] = index
        choice = options[index]
        if key is not None:
            st.session_state[key] = choice
        return choice

    monkeypatch.setattr(st, "selectbox", fake_selectbox)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)

    resolved = model_selector_component.model_selector()

    assert captured["index"] == 4
    assert resolved == config.GPT5_NANO
    assert st.session_state["model_override"] == config.GPT5_NANO
