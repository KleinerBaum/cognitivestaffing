"""Tests for the OpenAI LLM client helper."""

import json

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
