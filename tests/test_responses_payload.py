"""Tests for structured OpenAI payload helpers after Responses deprecation."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from typing import Any, Mapping

import pytest
from httpx import Response
from openai import BadRequestError, OpenAIError

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

    assert set(fmt.keys()) == {"type", "json_schema"}
    assert fmt["json_schema"]["name"] == "need_analysis_profile"

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
            "required": [],
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


def test_call_responses_safe_raises_unrecoverable_schema_short_circuit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unrecoverable schema errors should trigger explicit short-circuit handling."""

    fmt = openai_responses.build_json_schema_format(
        name="need_analysis_profile",
        schema={"type": "object"},
    )
    fake_response = cast(Response, SimpleNamespace(request=SimpleNamespace(), status_code=400, headers={}))

    def _raise_error(*_: Any, **__: Any) -> Any:
        raise BadRequestError(
            "invalid_json_schema: missing required schema fields",
            response=fake_response,
            body={"error": {"code": "invalid_json_schema"}},
        )

    monkeypatch.setattr(openai_responses, "call_responses", _raise_error)

    with pytest.raises(openai_responses.UnrecoverableSchemaShortCircuitError):
        openai_responses.call_responses_safe(
            messages=[{"role": "user", "content": "hi"}],
            model=model_config.GPT4O_MINI,
            response_format=fmt,
        )


def test_call_responses_rejects_mismatched_required_and_properties(monkeypatch: pytest.MonkeyPatch) -> None:
    """Responses call guard rejects object schemas with required/properties drift."""

    invoked = False

    def _fake_chat(*_: Any, **__: Any) -> _FakeChatResult:
        nonlocal invoked
        invoked = True
        return _FakeChatResult()

    monkeypatch.setattr(openai_responses, "call_chat_api", _fake_chat)

    class _Bundle:
        name = "need_analysis_profile"
        strict = True
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {"foo": {"type": "string"}},
            "required": [],
        }

    monkeypatch.setattr(openai_responses, "_build_schema_bundle_from_format", lambda _fmt: _Bundle())

    with pytest.raises(ValueError, match="mismatched required/properties"):
        openai_responses.call_responses(
            messages=[{"role": "user", "content": "hi"}],
            model=model_config.GPT4O_MINI,
            response_format={"type": "json_schema", "json_schema": {"name": "need_analysis_profile", "schema": {}}},
        )

    assert invoked is False


def test_call_responses_safe_raises_short_circuit_for_response_format_param_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """response_format schema-param BadRequest should short-circuit immediately."""

    fmt = openai_responses.build_json_schema_format(
        name="need_analysis_profile",
        schema={"type": "object"},
    )
    fake_response = cast(Response, SimpleNamespace(request=SimpleNamespace(), status_code=400, headers={}))

    def _raise_error(*_: Any, **__: Any) -> Any:
        raise BadRequestError(
            "Invalid schema for response_format 'need_analysis_profile'",
            response=fake_response,
            body={"error": {"param": "response_format"}},
        )

    monkeypatch.setattr(openai_responses, "call_responses", _raise_error)

    with pytest.raises(openai_responses.UnrecoverableSchemaShortCircuitError):
        openai_responses.call_responses_safe(
            messages=[{"role": "user", "content": "hi"}],
            model=model_config.GPT4O_MINI,
            response_format=fmt,
        )
