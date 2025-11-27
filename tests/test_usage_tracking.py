"""Regression tests for session-level token usage tracking.

The module exercises the following coverage points:
- ``StateKeys.USAGE`` aggregation across quick/precise chat calls and Responses
  helpers.
- Guard behaviour when ``OPENAI_API_KEY`` is missing (no usage increments).
- Sidebar usage rendering via ``_render_summary_context`` (totals + table).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from typing import Any

import pytest
import streamlit as st

import config

if not hasattr(config, "temporarily_force_classic_api"):

    @contextmanager
    def _noop_force_classic_api():  # pragma: no cover - import shim
        yield

    setattr(config, "temporarily_force_classic_api", _noop_force_classic_api)

from config.models import ModelTask
from constants.keys import StateKeys, UIKeys
from llm import openai_responses as responses_module
from llm.openai_responses import ResponsesCallResult
import openai_utils.api as openai_api
from openai_utils import ChatCallResult
from sidebar import SidebarContext, _render_summary_context
from utils.i18n import tr
from utils.usage import build_usage_markdown, usage_totals


def _seed_usage_state() -> dict[str, Any]:
    """Helper to initialise an empty usage block in ``st.session_state``."""

    usage_state: dict[str, Any] = {"input_tokens": 0, "output_tokens": 0, "by_task": {}}
    st.session_state[StateKeys.USAGE] = usage_state
    return usage_state


@pytest.fixture(autouse=True)
def _reset_session_state() -> None:
    """Ensure a clean Streamlit session for each test."""

    st.session_state.clear()
    yield
    st.session_state.clear()


def test_usage_counters_accumulate_across_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Coverage: quick/precise chat calls + Responses share the same usage counters."""

    st.session_state["lang"] = "en"
    _seed_usage_state()

    # Pretend credentials exist so the guard does not trigger.
    monkeypatch.setattr(openai_api, "OPENAI_API_KEY", "sk-test")

    chat_usages = [
        {"input_tokens": 42, "output_tokens": 8},
        {"input_tokens": 18, "output_tokens": 14},
    ]
    response_usage = {"input_tokens": 33, "output_tokens": 5}

    def _fake_chat_call(
        messages: Sequence[Mapping[str, Any]],
        *,
        task: ModelTask | str | None = None,
        **_: Any,
    ) -> ChatCallResult:
        usage = dict(chat_usages.pop(0))
        openai_api._update_usage_counters(usage, task=task)
        return ChatCallResult("stub", [], usage, response_id="chat-stub")

    def _fake_responses_call(
        messages: Sequence[Mapping[str, Any]],
        *,
        model: str,
        response_format: Mapping[str, Any],
        task: ModelTask | str | None = None,
        **_: Any,
    ) -> ResponsesCallResult:
        _ = (messages, model, response_format)
        usage = dict(response_usage)
        openai_api._update_usage_counters(usage, task=task)
        return ResponsesCallResult("{}", usage, "resp-stub", raw_response={})

    monkeypatch.setattr(openai_api, "call_chat_api", _fake_chat_call)
    monkeypatch.setattr(responses_module, "call_responses", _fake_responses_call)

    st.session_state[StateKeys.REASONING_MODE] = "quick"
    openai_api.call_chat_api([{"role": "user", "content": "hi"}], task=ModelTask.EXTRACTION)

    usage_state = st.session_state[StateKeys.USAGE]
    assert usage_state["input_tokens"] == 42
    assert usage_state["output_tokens"] == 8
    assert usage_state["by_task"][ModelTask.EXTRACTION.value] == {"input": 42, "output": 8}

    st.session_state[StateKeys.REASONING_MODE] = "precise"
    openai_api.call_chat_api([{"role": "user", "content": "hi again"}], task=ModelTask.JOB_AD)

    usage_state = st.session_state[StateKeys.USAGE]
    assert usage_state["input_tokens"] == 60
    assert usage_state["output_tokens"] == 22
    assert usage_state["by_task"][ModelTask.JOB_AD.value] == {"input": 18, "output": 14}

    responses_module.call_responses(
        [{"role": "system", "content": "schema"}],
        model="gpt-test",
        response_format={"type": "json_schema", "json_schema": {"name": "dummy", "schema": {}}},
        task=ModelTask.INTERVIEW_GUIDE,
    )

    usage_state = st.session_state[StateKeys.USAGE]
    assert usage_state["input_tokens"] == 93
    assert usage_state["output_tokens"] == 27
    assert usage_state["by_task"][ModelTask.INTERVIEW_GUIDE.value] == {"input": 33, "output": 5}


def test_missing_api_key_blocks_usage_updates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Coverage: guards prevent API execution + usage increments when key is missing."""

    st.session_state["lang"] = "en"
    _seed_usage_state()

    monkeypatch.setattr(openai_api, "OPENAI_API_KEY", "")
    monkeypatch.setattr(openai_api, "client", None, raising=False)

    recorded_errors: list[str] = []
    monkeypatch.setattr(openai_api, "display_error", recorded_errors.append)
    monkeypatch.setattr(st, "error", recorded_errors.append)

    with pytest.raises(RuntimeError):
        openai_api.call_chat_api([{"role": "user", "content": "block chat"}])

    response_format = {"type": "json_schema", "json_schema": {"name": "stub", "schema": {}}}
    with pytest.raises(RuntimeError):
        responses_module.call_responses(
            [{"role": "user", "content": "block responses"}],
            model="gpt-test",
            response_format=response_format,
        )

    usage_state = st.session_state[StateKeys.USAGE]
    assert usage_state["input_tokens"] == 0
    assert usage_state["output_tokens"] == 0
    assert usage_state["by_task"] == {}


def test_sidebar_usage_expander_matches_totals(monkeypatch: pytest.MonkeyPatch) -> None:
    """Coverage: sidebar summary expander mirrors ``usage_totals`` + markdown helper."""

    st.session_state["lang"] = "en"
    usage_state = {
        "input_tokens": 15,
        "output_tokens": 9,
        "by_task": {
            ModelTask.EXTRACTION.value: {"input": 10, "output": 4},
            ModelTask.JOB_AD.value: {"input": 5, "output": 5},
        },
    }
    st.session_state[StateKeys.USAGE] = usage_state
    st.session_state[UIKeys.JOB_AD_OUTPUT] = True
    st.session_state[UIKeys.INTERVIEW_OUTPUT] = False

    context = SidebarContext(
        profile={},
        extraction_summary={},
        skill_buckets={},
        missing_fields=set(),
        missing_by_section={},
        prefilled_sections=[],
    )

    active_expanders: list[str] = []
    captured_summary: dict[str, str | None] = {"label": None, "table": None}

    class _DummyExpander:
        def __init__(self, label: str) -> None:
            captured_summary["label"] = label
            self._label = label

        def __enter__(self) -> "_DummyExpander":
            active_expanders.append(self._label)
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            active_expanders.pop()

    def _fake_expander(label: str, *args: Any, **kwargs: Any) -> _DummyExpander:
        _ = (args, kwargs)
        return _DummyExpander(label)

    def _fake_markdown(text: Any, *args: Any, **kwargs: Any) -> None:
        _ = (args, kwargs)
        if active_expanders:
            captured_summary["table"] = str(text)

    monkeypatch.setattr(st, "expander", _fake_expander)
    monkeypatch.setattr(st, "markdown", _fake_markdown)

    _render_summary_context(context)

    in_tokens, out_tokens, total_tokens = usage_totals(usage_state)
    expected_label = tr("Tokenverbrauch", "Token usage") + f": {in_tokens} + {out_tokens} = {total_tokens}"
    assert captured_summary["label"] == expected_label
    assert captured_summary["table"] == build_usage_markdown(usage_state)
