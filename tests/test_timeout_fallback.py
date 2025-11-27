"""Timeout recovery behaviour for OpenAI chat calls."""

from __future__ import annotations

import types
from typing import Any

import pytest
import streamlit as st
from openai import APITimeoutError

import config
from openai_utils import api as openai_api
from constants.keys import StateKeys


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    """Ensure model availability and session state are clean before each test."""

    try:
        st.session_state.clear()
    except Exception:  # pragma: no cover - Streamlit session may not exist
        pass
    try:
        st.session_state[StateKeys.REASONING_MODE] = "quick"
    except Exception:  # pragma: no cover - Streamlit session may not exist
        pass
    config.clear_unavailable_models()
    yield
    config.clear_unavailable_models()


def test_timeout_marks_model_unavailable_and_falls_back(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A timeout should mark the model unavailable and move to the next candidate."""

    caplog.set_level("WARNING", logger="cognitive_needs.openai")
    candidates = config.get_model_candidates(config.ModelTask.EXTRACTION)
    assert len(candidates) >= 2, "Expected at least one fallback candidate"
    attempts: list[str | None] = []

    def _fake_create_response(payload: dict[str, Any], *, api_mode: str) -> Any:
        model = payload.get("model")
        attempts.append(model)
        if len(attempts) == 1:
            raise APITimeoutError("Request timed out.")
        return types.SimpleNamespace(
            output_text="OK",
            output=[],
            usage={"input_tokens": 1, "output_tokens": 1},
            id="resp-final",
        )

    monkeypatch.setattr(openai_api, "_llm_disabled", lambda: False)
    monkeypatch.setattr(openai_api.openai_client, "_create_response_with_timeout", _fake_create_response)

    result = openai_api.call_chat_api(
        messages=[{"role": "user", "content": "hi"}],
        task=config.ModelTask.EXTRACTION,
    )

    assert result.content == "OK"
    assert len(attempts) == 2
    assert attempts[0] != attempts[1]
    assert not config.is_model_available(attempts[0] or "")
    assert config.get_model_for(config.ModelTask.EXTRACTION) == attempts[1]
    timeout_logs = [record for record in caplog.records if "timeout" in record.message.lower()]
    assert len(timeout_logs) == 1

