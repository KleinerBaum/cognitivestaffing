from __future__ import annotations

import streamlit as st
from openai import OpenAIError

import openai_utils.api as api
from openai_utils.errors import ExternalServiceError


class DummyQuotaError(OpenAIError):
    def __init__(self, message: str, code: str | None = None, payload: dict | None = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if payload is not None:
            self.error = payload


class DummyRateLimitError(OpenAIError):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def test_quota_error_sets_session_flag_and_stops_retries() -> None:
    st.session_state.clear()
    error = DummyQuotaError("You exceeded your current quota.", payload={"code": "insufficient_quota"})

    assert api._is_quota_exceeded_error(error) is True
    assert api._should_abort_retry(error) is True
    assert st.session_state["openai_unavailable"] is True
    assert st.session_state["openai_unavailable_reason"] == "insufficient_quota"


def test_wrap_openai_exception_surfaces_quota_message() -> None:
    st.session_state.clear()
    error = DummyQuotaError("You exceeded your current quota.", code="insufficient_quota")

    wrapped = api._wrap_openai_exception(
        error,
        model="gpt-test",
        schema_name="schema",
        step="example",
        api_mode="chat",
    )

    assert isinstance(wrapped, ExternalServiceError)
    assert wrapped.message in api._QUOTA_EXCEEDED_MESSAGE
    assert st.session_state["openai_unavailable"] is True


def test_rate_limit_error_does_not_mark_quota_unavailable() -> None:
    st.session_state.clear()
    error = DummyRateLimitError("HTTP 429 Too Many Requests")

    assert api._is_quota_exceeded_error(error) is False
    assert api._should_abort_retry(error) is False
    assert st.session_state.get("openai_unavailable", False) is False
