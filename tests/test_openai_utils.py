import pytest

import openai_utils
from openai_utils import call_chat_api, extract_with_function


def test_call_chat_api_raises_when_no_api_key(monkeypatch):
    """call_chat_api should raise if OpenAI API key is missing."""
    monkeypatch.setattr("openai_utils.OPENAI_API_KEY", "")
    monkeypatch.setattr("openai_utils.client", None, raising=False)

    with pytest.raises(RuntimeError):
        call_chat_api([{"role": "user", "content": "hi"}])


def test_call_chat_api_function_call(monkeypatch):
    """Function call arguments should be accessible on the returned message."""

    class _FakeFunctionCall:
        def __init__(self, arguments: str | None = None) -> None:
            self.arguments = arguments

    class _FakeMessage:
        def __init__(self) -> None:
            self.content = None
            self.function_call = _FakeFunctionCall('{"job_title": "x"}')

    class _FakeResponse:
        def __init__(self) -> None:
            self.choices = [type("Choice", (), {"message": _FakeMessage()})()]

    class _FakeCompletions:
        @staticmethod
        def create(**kwargs):
            return _FakeResponse()

    class _FakeClient:
        chat = type("Chat", (), {"completions": _FakeCompletions()})()

    monkeypatch.setattr("openai_utils.client", _FakeClient(), raising=False)
    out = call_chat_api([], functions=[{}], function_call={"name": "fn"})
    assert out.function_call.arguments == '{"job_title": "x"}'


def test_extract_with_function(monkeypatch):
    """extract_with_function should parse JSON from a function call."""

    class _FakeMessage:
        def __init__(self) -> None:
            self.content = None
            self.function_call = {"arguments": '{"job_title": "Dev"}'}

    monkeypatch.setattr(openai_utils, "call_chat_api", lambda *a, **k: _FakeMessage())
    from core import schema as cs

    monkeypatch.setattr(cs, "coerce_and_fill", lambda model, raw: raw)
    monkeypatch.setattr(cs, "VacalyserJD", object())

    result = extract_with_function("text", {})
    assert result["job_title"] == "Dev"
