"""Tests for hardened OpenAI Responses payload generation (v2025)."""

from __future__ import annotations

from types import SimpleNamespace
from contextlib import contextmanager
from typing import Any, Mapping

import pytest
from openai import OpenAIError

from llm import openai_responses


class _FakeResponsesClient:
    """Simple stub capturing the last payload passed to responses.create."""

    def __init__(self) -> None:
        self.captured: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> Any:  # pragma: no cover - simple stub
        self.captured = dict(kwargs)
        return SimpleNamespace(
            output=[],
            output_text="{}",
            usage={},
            id="resp-test",
        )


class _FakeClient:
    def __init__(self, responses_client: _FakeResponsesClient) -> None:
        self.responses = responses_client


@pytest.fixture(autouse=True)
def _patch_client(monkeypatch: pytest.MonkeyPatch) -> _FakeResponsesClient:
    """Provide a fake OpenAI client for each test."""

    fake_responses = _FakeResponsesClient()
    monkeypatch.setattr(openai_responses, "get_client", lambda: _FakeClient(fake_responses))
    return fake_responses


def test_v2025_minimal_payload(_patch_client: _FakeResponsesClient) -> None:
    """Payloads must stick to the minimal v2025 schema contract."""

    fmt = openai_responses.build_json_schema_format(
        name="need_analysis_profile",
        schema={"type": "object"},
    )
    result = openai_responses.call_responses(
        messages=[{"role": "user", "content": "hi"}],
        model="gpt-4o-mini",
        response_format=fmt,
    )

    assert result.response_id == "resp-test"

    captured = _patch_client.captured
    assert captured is not None, "Expected responses.create to be invoked"
    assert set(captured) == {"model", "input", "timeout", "text"}
    assert captured["model"] == "gpt-4o-mini"
    assert isinstance(captured["input"], list)
    assert captured["timeout"] == openai_responses.OPENAI_REQUEST_TIMEOUT

    text_section = captured["text"]
    assert set(text_section) == {"format"}
    format_payload = text_section["format"]
    assert format_payload["type"] == "json_schema"
    assert format_payload["name"] == "need_analysis_profile"
    assert format_payload["schema"] == {
        "type": "object",
        "additionalProperties": False,
    }


def test_schema_guard_triggers_fallback(monkeypatch: pytest.MonkeyPatch, _patch_client: _FakeResponsesClient) -> None:
    """Missing schemas must be caught before dispatch (RESPONSES_PAYLOAD_GUARD)."""

    fmt: Mapping[str, Any] = {"name": "broken", "schema": None}

    dispatched = False

    def _fail_create(**_: Any) -> None:  # pragma: no cover - guard ensures no call
        nonlocal dispatched
        dispatched = True

    monkeypatch.setattr(_patch_client, "create", _fail_create)

    result = openai_responses.call_responses_safe(
        messages=[{"role": "user", "content": "hi"}],
        model="gpt-4o-mini",
        response_format=fmt,
    )

    assert result is None
    assert dispatched is False


def test_schema_guard_requires_name(monkeypatch: pytest.MonkeyPatch, _patch_client: _FakeResponsesClient) -> None:
    """Schemas must include a non-empty name to pass validation."""

    fmt: Mapping[str, Any] = {"json_schema": {"schema": {"type": "object"}}}

    dispatched = False

    def _fail_create(**_: Any) -> None:  # pragma: no cover - guard ensures no call
        nonlocal dispatched
        dispatched = True

    monkeypatch.setattr(_patch_client, "create", _fail_create)

    result = openai_responses.call_responses_safe(
        messages=[{"role": "user", "content": "hi"}],
        model="gpt-4o-mini",
        response_format=fmt,
    )

    assert result is None
    assert dispatched is False


def test_call_responses_safe_retries_with_chat_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """call_responses_safe should invoke the chat fallback once on Responses errors."""

    fmt = openai_responses.build_json_schema_format(
        name="need_analysis_profile",
        schema={"type": "object"},
    )

    def _raise_error(*_: Any, **__: Any) -> Any:
        raise OpenAIError("boom")

    fallback_calls = {"count": 0}

    class _FakeChatResult:
        def __init__(self) -> None:
            self.content = "fallback"
            self.usage = {"input_tokens": 1}
            self.response_id = "chat-123"
            self.raw_response = {"id": "chat-123"}

    def _fake_chat(*_: Any, **__: Any) -> _FakeChatResult:
        fallback_calls["count"] += 1
        return _FakeChatResult()

    @contextmanager
    def _noop_context() -> Any:
        yield

    monkeypatch.setattr(openai_responses, "call_responses", _raise_error)
    monkeypatch.setattr(openai_responses, "call_chat_api", _fake_chat)
    monkeypatch.setattr(openai_responses, "temporarily_force_classic_api", _noop_context)

    result = openai_responses.call_responses_safe(
        messages=[{"role": "user", "content": "hi"}],
        model="gpt-4o-mini",
        response_format=fmt,
    )

    assert result is not None
    assert result.used_chat_fallback is True
    assert result.content == "fallback"
    assert fallback_calls["count"] == 1


def test_chat_fallback_strips_strict_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chat fallback must remove the strict flag before hitting the Chat API."""

    fmt = openai_responses.build_json_schema_format(
        name="need_analysis_profile",
        schema={"type": "object"},
        strict=True,
    )

    captured: dict[str, Any] = {}

    def _raise_error(*_: Any, **__: Any) -> Any:
        raise OpenAIError("boom")

    class _FakeChatResult:
        def __init__(self) -> None:
            self.content = "fallback"
            self.usage = {"input_tokens": 1}
            self.response_id = "chat-456"
            self.raw_response = {"id": "chat-456"}

    def _fake_chat(*_: Any, **kwargs: Any) -> _FakeChatResult:
        captured.update(kwargs)
        return _FakeChatResult()

    @contextmanager
    def _noop_context() -> Any:
        yield

    monkeypatch.setattr(openai_responses, "call_responses", _raise_error)
    monkeypatch.setattr(openai_responses, "call_chat_api", _fake_chat)
    monkeypatch.setattr(openai_responses, "temporarily_force_classic_api", _noop_context)

    result = openai_responses.call_responses_safe(
        messages=[{"role": "user", "content": "hi"}],
        model="gpt-4o-mini",
        response_format=fmt,
    )

    assert result is not None
    assert captured["json_schema"] == {
        "name": "need_analysis_profile",
        "schema": {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "additionalProperties": False,
        },
    }
    assert "strict" not in captured["json_schema"]


def test_function_call_chat_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Function-call fallback should mirror the schema via chat completions."""

    fmt = openai_responses.build_json_schema_format(
        name="need_analysis_profile",
        schema={"type": "object", "properties": {"company": {"type": "string"}}, "required": ["company"]},
    )

    def _raise_error(*_: Any, **__: Any) -> Any:
        raise OpenAIError("boom")

    @contextmanager
    def _noop_context() -> Any:
        yield

    class _FakeCompletions:
        def __init__(self) -> None:
            self.captured: dict[str, Any] | None = None

        def create(self, **kwargs: Any) -> Any:
            self.captured = dict(kwargs)
            return SimpleNamespace(
                id="chat-func",
                choices=[
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": "extract_profile",
                                        "arguments": '{"company": "ACME"}',
                                    }
                                }
                            ]
                        }
                    }
                ],
                usage={"prompt_tokens": 10, "completion_tokens": 5},
            )

    class _FakeChat:
        def __init__(self) -> None:
            self.completions = _FakeCompletions()

    class _FakeClient:
        def __init__(self) -> None:
            self.chat = _FakeChat()

    fake_client = _FakeClient()

    def _fail_chat(*_: Any, **__: Any) -> None:
        raise AssertionError("chat fallback not expected")

    monkeypatch.setattr(openai_responses, "call_responses", _raise_error)
    monkeypatch.setattr(openai_responses, "call_chat_api", _fail_chat)
    monkeypatch.setattr(openai_responses, "temporarily_force_classic_api", _noop_context)
    monkeypatch.setattr(openai_responses, "get_client", lambda: fake_client)
    monkeypatch.setattr(openai_responses.app_config, "SCHEMA_FUNCTION_FALLBACK", True)

    result = openai_responses.call_responses_safe(
        messages=[{"role": "user", "content": "hi"}],
        model="gpt-4o-mini",
        response_format=fmt,
        allow_empty=False,
    )

    assert result is not None
    assert result.used_chat_fallback is True
    assert result.content == '{"company": "ACME"}'
    assert result.usage.get("prompt_tokens") == 10
    assert result.usage.get("completion_tokens") == 5

    captured = fake_client.chat.completions.captured
    assert captured is not None
    assert captured["function_call"] == {"name": "extract_profile"}
    assert captured["functions"][0]["parameters"]["properties"] == {"company": {"type": "string"}}


def test_temperature_omitted_when_unsupported(
    monkeypatch: pytest.MonkeyPatch, _patch_client: _FakeResponsesClient
) -> None:
    """Temperature should be absent when the model rejects it (TEMP_SUPPORTED)."""

    monkeypatch.setattr(openai_responses, "model_supports_temperature", lambda model: False)

    fmt = openai_responses.build_json_schema_format(
        name="need_analysis_profile",
        schema={"type": "object"},
    )

    openai_responses.call_responses(
        messages=[{"role": "user", "content": "hi"}],
        model="o1-mini",
        response_format=fmt,
        temperature=0.7,
    )

    captured = _patch_client.captured
    assert captured is not None
    assert "temperature" not in captured
