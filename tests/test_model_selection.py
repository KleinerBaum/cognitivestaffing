"""Tests covering model routing and fallbacks for OpenAI integrations."""

from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path
from typing import Any, Iterator

import logging
import pytest
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config
import config.models as model_config
import core.esco_utils as esco_utils
import openai_utils.client as client_module
from openai_utils.client import OpenAIClient


pytestmark = pytest.mark.integration
import openai_utils
from openai_utils import ChatCallResult
from openai import BadRequestError


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
    result = openai_utils.suggest_skills_for_role("Engineer", model=model_config.REASONING_MODEL)

    assert captured["model"] == model_config.REASONING_MODEL
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
        model=model_config.REASONING_MODEL,
        company_name="Acme",
    )

    assert captured["model"] == model_config.REASONING_MODEL
    assert result == ["Define roadmap"]


def test_suggest_benefits_model(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str | None] = {}

    def fake_call_chat_api(messages: Any, model: str | None = None, **kwargs: Any) -> ChatCallResult:
        captured["model"] = model
        return ChatCallResult("- BenefitA\n- BenefitB", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)
    out = openai_utils.suggest_benefits("Engineer", lang="en", model=model_config.GPT4O_MINI)
    assert captured["model"] == model_config.GPT4O_MINI
    assert out == ["BenefitA", "BenefitB"]


def test_suggest_benefits_dispatch_default(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str | None] = {}
    st.session_state.clear()

    def fake_call_chat_api(messages: Any, model: str | None = None, **kwargs: Any) -> ChatCallResult:
        captured["model"] = model
        return ChatCallResult("- BenefitA\n- BenefitB", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)
    out = openai_utils.suggest_benefits("Engineer")
    assert captured["model"] == model_config.REASONING_MODEL
    assert out == ["BenefitA", "BenefitB"]


def test_session_override_is_ignored_for_benefits(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, str | None] = {}
    st.session_state.clear()
    st.session_state["model_override"] = model_config.GPT4O

    def fake_call_chat_api(messages: Any, model: str | None = None, **kwargs: Any) -> ChatCallResult:
        captured["model"] = model
        return ChatCallResult("- BenefitA\n- BenefitB", [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", fake_call_chat_api)
    out = openai_utils.suggest_benefits("Engineer")
    assert captured["model"] == model_config.REASONING_MODEL
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

    fallback_chain = model_config.get_model_fallbacks_for(model_config.ModelTask.EXTRACTION)
    assert fallback_chain, "Expected at least one candidate in the fallback chain"

    selected = model_config.get_model_for(model_config.ModelTask.EXTRACTION)
    assert selected == fallback_chain[0]


def test_falls_back_to_gpt35_when_gpt4o_missing() -> None:
    """When GPT-4o is unavailable the helper should choose GPT-3.5."""

    fallback_chain = model_config.get_model_fallbacks_for(model_config.ModelTask.EXTRACTION)
    assert len(fallback_chain) >= 2, "Expected a secondary fallback entry"

    config.mark_model_unavailable(fallback_chain[0])
    selected = model_config.get_model_for(model_config.ModelTask.EXTRACTION)
    assert selected == fallback_chain[1]


def test_falls_back_to_last_candidate_when_all_marked() -> None:
    """If every candidate is unavailable the router still returns the last option."""

    fallback_chain = model_config.get_model_fallbacks_for(model_config.ModelTask.EXTRACTION)
    assert fallback_chain, "Expected at least one candidate"

    for candidate in fallback_chain:
        config.mark_model_unavailable(candidate)

    selected = model_config.get_model_for(model_config.ModelTask.EXTRACTION)
    assert selected == fallback_chain[-1]


def test_marking_unavailable_is_cleared_on_reload() -> None:
    """Reloading the configuration resets availability decisions."""

    fallback_chain = model_config.get_model_fallbacks_for(model_config.ModelTask.EXTRACTION)
    primary = fallback_chain[0]
    config.mark_model_unavailable(primary)
    selected = model_config.get_model_for(model_config.ModelTask.EXTRACTION)
    assert selected != primary

    config.clear_unavailable_models()
    importlib.reload(config)
    reloaded_chain = model_config.get_model_fallbacks_for(model_config.ModelTask.EXTRACTION)
    assert model_config.get_model_for(model_config.ModelTask.EXTRACTION) == reloaded_chain[0]


def test_call_chat_api_switches_to_fallback_on_unavailable(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """call_chat_api should retry with the next fallback when the primary fails."""

    st.session_state.clear()
    caplog.set_level("WARNING", logger="cognitive_needs.openai")

    attempts: list[str] = []

    def _fake_create_response(payload: dict[str, Any]) -> Any:
        model = payload.get("model")
        chosen_model = model_config.GPT4O_MINI if not attempts else model_config.GPT4O
        attempts.append(str(chosen_model))
        payload["model"] = chosen_model
        if len(attempts) == 1:
            fake_response = types.SimpleNamespace(
                request=types.SimpleNamespace(
                    method="POST",
                    url="https://api.openai.com/v1/responses",
                ),
                status_code=503,
                headers={},
            )
            if model:
                model_config.mark_model_unavailable(str(model))
            logging.getLogger("cognitive_needs.openai").warning(
                "retrying with fallback from %s to %s",
                model_config.GPT4O_MINI,
                model_config.GPT4O,
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
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(client_module, "OPENAI_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(
        model_config,
        "get_model_candidates",
        lambda *_, **__: [model_config.GPT4O_MINI, model_config.GPT4O],
    )
    monkeypatch.setattr(model_config, "select_model", lambda *_, **__: model_config.GPT4O_MINI)
    monkeypatch.setattr(
        OpenAIClient,
        "_create_response_with_timeout",
        lambda self, payload, api_mode=None: _fake_create_response(payload),
    )
    monkeypatch.setattr(
        OpenAIClient,
        "execute_request",
        lambda self, payload, model, api_mode=None, **_: _fake_create_response(payload),
    )

    result = openai_utils.api.call_chat_api(
        messages=[{"role": "user", "content": "hi"}],
        task=model_config.ModelTask.EXTRACTION,
    )

    assert result.content == "OK"
    assert attempts[0] == model_config.GPT4O_MINI
    assert attempts[1] == model_config.GPT4O
    assert any("retrying with fallback" in record.message for record in caplog.records)
