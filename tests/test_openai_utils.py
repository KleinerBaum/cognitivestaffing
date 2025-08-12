import pytest

from openai_utils import call_chat_api


def test_call_chat_api_raises_when_no_api_key(monkeypatch):
    """call_chat_api should raise if OpenAI API key is missing."""
    monkeypatch.setattr("openai_utils.OPENAI_API_KEY", "")
    monkeypatch.setattr("openai_utils.client", None, raising=False)

    with pytest.raises(RuntimeError):
        call_chat_api([{"role": "user", "content": "hi"}])


def test_call_chat_api_function_call(monkeypatch):
    """Function call arguments should be returned when provided."""

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
    assert out == '{"job_title": "x"}'
