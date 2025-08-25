"""Tests for the OpenAI LLM client helper."""

import json

import pytest

import llm.client as client


class _FakeFunctionCall:
    """Minimal stand-in for OpenAI function call payload."""

    def __init__(self, arguments: str | None = None) -> None:
        self.arguments = arguments


class _FakeMessage:
    """Minimal message object returned by the OpenAI client."""

    def __init__(
        self, content: str = "", function_call: _FakeFunctionCall | None = None
    ) -> None:
        self.content = content
        self.function_call = function_call


class _FakeChoice:
    """Container mimicking a chat completion choice."""

    def __init__(self, message: _FakeMessage) -> None:
        self.message = message


class _FakeResponse:
    """Simplified response holding a single choice."""

    def __init__(self, message: _FakeMessage) -> None:
        self.choices = [_FakeChoice(message)]


def fake_create(**kwargs):  # noqa: D401
    """Return a fake OpenAI response object."""

    if client.MODE == "function":
        msg = _FakeMessage(
            function_call=_FakeFunctionCall(arguments=json.dumps({"job_title": "x"}))
        )
        return _FakeResponse(msg)
    return _FakeResponse(_FakeMessage(content="{}"))


def test_extract_json_smoke(monkeypatch):
    """Smoke test for the extraction helper."""

    monkeypatch.setattr(client.OPENAI_CLIENT.chat.completions, "create", fake_create)
    out = client.extract_json("text")
    assert isinstance(out, str) and out != ""


def test_assert_closed_schema_raises() -> None:
    """The helper should detect foreign key references."""

    with pytest.raises(ValueError):
        client._assert_closed_schema({"$ref": "#/foo"})


def test_generate_error_report_missing_required() -> None:
    """With no mandatory fields, the report should be empty."""

    report = client._generate_error_report({"position": {"job_title": "x"}})
    assert report == ""
