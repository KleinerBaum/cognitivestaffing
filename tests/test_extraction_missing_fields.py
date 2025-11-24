from __future__ import annotations

from typing import Any

import pytest
import streamlit as st

import openai_utils
from constants.keys import StateKeys
from openai_utils import ChatCallResult


def _fake_response(payload: dict[str, Any]) -> ChatCallResult:
    return ChatCallResult(None, [{"function": {"input": payload}}], {})


def test_validation_error_marks_missing_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM validation issues should not crash and mark missing critical fields."""

    st.session_state.clear()

    invalid_payload = {"company": {"name": []}}

    def _fake_call(messages, **kwargs) -> ChatCallResult:  # noqa: ANN001 - API signature is dynamic
        return _fake_response(invalid_payload)

    monkeypatch.setattr(openai_utils.api, "call_chat_api", _fake_call)
    monkeypatch.setattr(openai_utils.extraction, "apply_basic_fallbacks", lambda profile, *_args, **_kwargs: profile)

    result = openai_utils.extract_with_function("ignored", {})

    assert result.data["company"]["name"] in (None, "")
    missing = st.session_state.get(StateKeys.EXTRACTION_MISSING) or []
    assert "company.name" in missing


def test_invalid_field_metadata_marks_missing_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid fields detected during normalization should surface to the UI."""

    st.session_state.clear()

    payload_with_missing = {"company": {}, "position": {"job_title": "Engineer"}}

    def _fake_call(messages, **kwargs) -> ChatCallResult:  # noqa: ANN001 - API signature is dynamic
        return _fake_response(payload_with_missing)

    monkeypatch.setattr(openai_utils.api, "call_chat_api", _fake_call)
    monkeypatch.setattr(openai_utils.extraction, "apply_basic_fallbacks", lambda profile, *_args, **_kwargs: profile)

    result = openai_utils.extract_with_function("ignored", {})

    assert result.data["position"]["job_title"] == "Engineer"
    missing = st.session_state.get(StateKeys.EXTRACTION_MISSING) or []
    assert "company.name" in missing
