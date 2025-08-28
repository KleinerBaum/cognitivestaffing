import pytest

import openai_utils
from openai_utils import ChatCallResult, call_chat_api, extract_with_function


def test_call_chat_api_raises_when_no_api_key(monkeypatch):
    """call_chat_api should raise if OpenAI API key is missing."""
    monkeypatch.setattr("openai_utils.OPENAI_API_KEY", "")
    monkeypatch.setattr("openai_utils.client", None, raising=False)

    with pytest.raises(RuntimeError):
        call_chat_api([{"role": "user", "content": "hi"}])


def test_call_chat_api_function_call(monkeypatch):
    """Function call arguments should be accessible on the returned message."""

    class _FakeResponse:
        def __init__(self) -> None:
            self.output: list[dict[str, str]] = [
                {
                    "type": "function_call",
                    "name": "fn",
                    "arguments": '{"job_title": "x"}',
                }
            ]
            self.output_text = ""
            self.usage: dict[str, int] = {}

    class _FakeResponses:
        @staticmethod
        def create(**kwargs):
            return _FakeResponse()

    class _FakeClient:
        responses = _FakeResponses()

    monkeypatch.setattr("openai_utils.client", _FakeClient(), raising=False)
    out = call_chat_api(
        [],
        tools=[{"type": "function", "name": "fn", "parameters": {}}],
        tool_choice={"type": "function", "name": "fn"},
    )
    assert out.function_call and out.function_call["arguments"] == '{"job_title": "x"}'


def test_extract_with_function(monkeypatch):
    """extract_with_function should parse JSON from a function call."""

    monkeypatch.setattr(
        openai_utils,
        "call_chat_api",
        lambda *a, **k: ChatCallResult(
            None, [], {"arguments": '{"job_title": "Dev"}'}, {}
        ),
    )
    from core import schema as cs

    class _FakeJD:
        def __init__(self, data: dict[str, str]) -> None:
            self._data = data

        def model_dump(self) -> dict[str, str]:
            return self._data

    monkeypatch.setattr(cs, "coerce_and_fill", lambda data: _FakeJD(data))

    result = extract_with_function("text", {})
    assert result["job_title"] == "Dev"
