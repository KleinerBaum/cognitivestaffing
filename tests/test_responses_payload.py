"""Tests for structured OpenAI payload helpers after Responses deprecation."""

from __future__ import annotations

from typing import Any, Mapping

import pytest
from openai import OpenAIError

import config.models as model_config
from llm import openai_responses


class _FakeChatResult:
    def __init__(self, content: str = "{}") -> None:
        self.content = content
        self.usage = {"input_tokens": 1}
        self.response_id = "chat-123"
        self.raw_response = {"id": self.response_id}
        self.tool_calls: list[Any] = []


def test_call_responses_builds_chat_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """call_responses should construct a chat payload with JSON schema metadata."""

    fmt = openai_responses.build_json_schema_format(
        name="need_analysis_profile",
        schema={"type": "object"},
        strict=True,
    )

    captured: dict[str, Any] = {}

    def _fake_chat(messages: Any, **kwargs: Any) -> _FakeChatResult:
        captured["messages"] = messages
        captured.update(kwargs)
        return _FakeChatResult('{"ok": true}')

    monkeypatch.setattr(openai_responses, "call_chat_api", _fake_chat)

    result = openai_responses.call_responses(
        messages=[{"role": "user", "content": "hi"}],
        model=model_config.GPT4O_MINI,
        response_format=fmt,
        temperature=0.0,
        max_completion_tokens=128,
        reasoning_effort="low",
        verbosity="concise",
        task="extraction",
    )

    assert result.content == '{"ok": true}'
    assert captured["model"] == model_config.GPT4O_MINI
    assert captured["max_completion_tokens"] == 128
    assert captured["temperature"] == 0.0
    assert captured["reasoning_effort"] == "low"
    assert captured["verbosity"] == "concise"
    assert captured["task"] == "extraction"
    assert captured["json_schema"] == {
        "name": "need_analysis_profile",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "$schema": "http://json-schema.org/draft-07/schema#",
        },
        "strict": True,
    }
    assert captured["use_response_format"] is True
    assert captured["include_raw_response"] is True
    assert captured["messages"][0]["role"] == "system"


def test_call_responses_safe_blocks_invalid_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid schema payloads should not trigger any chat call."""

    fmt: Mapping[str, Any] = {"name": "broken", "schema": None}
    invoked = False

    def _fake_chat(*_: Any, **__: Any) -> _FakeChatResult:
        nonlocal invoked
        invoked = True
        return _FakeChatResult()

    monkeypatch.setattr(openai_responses, "call_chat_api", _fake_chat)

    result = openai_responses.call_responses_safe(
        messages=[{"role": "user", "content": "hi"}],
        model=model_config.GPT4O_MINI,
        response_format=fmt,
    )

    assert result is None
    assert invoked is False


def test_call_responses_safe_returns_none_on_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Invalid JSON payloads should return ``None`` without a secondary call."""

    fmt = openai_responses.build_json_schema_format(
        name="need_analysis_profile",
        schema={"type": "object"},
    )

    def _fake_call(*_: Any, **__: Any) -> openai_responses.ResponsesCallResult:
        return openai_responses.ResponsesCallResult(
            content="not-json",
            usage={},
            response_id="resp-1",
            raw_response={},
        )

    monkeypatch.setattr(openai_responses, "call_responses", _fake_call)

    result = openai_responses.call_responses_safe(
        messages=[{"role": "user", "content": "hi"}],
        model=model_config.GPT4O_MINI,
        response_format=fmt,
    )

    assert result is None


def test_call_responses_safe_propagates_api_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """API errors should be surfaced as ``None`` without retries."""

    fmt = openai_responses.build_json_schema_format(
        name="need_analysis_profile",
        schema={"type": "object"},
    )

    def _raise_error(*_: Any, **__: Any) -> Any:
        raise OpenAIError("boom")

    monkeypatch.setattr(openai_responses, "call_responses", _raise_error)

    result = openai_responses.call_responses_safe(
        messages=[{"role": "user", "content": "hi"}],
        model=model_config.GPT4O_MINI,
        response_format=fmt,
    )

    assert result is None
