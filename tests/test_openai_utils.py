import pytest

from typing import Any

import openai_utils
from openai_utils import ChatCallResult, call_chat_api, extract_with_function


def test_call_chat_api_raises_when_no_api_key(monkeypatch):
    """call_chat_api should raise if OpenAI API key is missing."""
    monkeypatch.setattr("openai_utils.OPENAI_API_KEY", "")
    monkeypatch.setattr("openai_utils.client", None, raising=False)

    with pytest.raises(RuntimeError):
        call_chat_api([{"role": "user", "content": "hi"}])


def test_call_chat_api_tool_call(monkeypatch):
    """Tool call information should be returned to the caller."""

    class _FakeResponse:
        def __init__(self) -> None:
            self.output: list[dict[str, Any]] = [
                {
                    "type": "tool_call",
                    "id": "1",
                    "function": {
                        "name": "fn",
                        "arguments": '{"job_title": "x"}',
                    },
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
        tools=[{"type": "function", "function": {"name": "fn", "parameters": {}}}],
        tool_choice={"type": "function", "name": "fn"},
    )
    assert out.tool_calls[0]["function"]["arguments"] == '{"job_title": "x"}'


def test_extract_with_function(monkeypatch):
    """extract_with_function should parse JSON from a function call."""

    monkeypatch.setattr(
        openai_utils,
        "call_chat_api",
        lambda *a, **k: ChatCallResult(
            None, [{"function": {"arguments": '{"job_title": "Dev"}'}}], {}
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


def test_call_chat_api_executes_tool(monkeypatch):
    """call_chat_api should execute mapped tools and return final content."""

    from core import analysis_tools

    class _FirstResponse:
        def __init__(self) -> None:
            self.output = [
                {
                    "type": "tool_call",
                    "id": "1",
                    "function": {
                        "name": "get_salary_benchmark",
                        "arguments": '{"role": "software developer", "country": "US"}',
                    },
                }
            ]
            self.output_text = ""
            self.usage: dict[str, int] = {}

    class _SecondResponse:
        def __init__(self) -> None:
            self.output: list[dict[str, Any]] = []
            self.output_text = "done"
            self.usage: dict[str, int] = {}

    class _FakeResponses:
        def __init__(self) -> None:
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return _FirstResponse()
            assert kwargs["input"][1]["role"] == "tool"
            return _SecondResponse()

    class _FakeClient:
        responses = _FakeResponses()

    monkeypatch.setattr("openai_utils.client", _FakeClient(), raising=False)
    tools, funcs = analysis_tools.build_analysis_tools()
    res = call_chat_api(
        [{"role": "user", "content": "hi"}],
        tools=tools,
        tool_functions=funcs,
    )
    assert res.content == "done"
    assert res.tool_calls[0]["function"]["name"] == "get_salary_benchmark"
