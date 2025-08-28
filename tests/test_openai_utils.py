import pytest

from typing import Any

import httpx
import openai_utils
from openai_utils import ChatCallResult, call_chat_api, extract_with_function
from openai import AuthenticationError, RateLimitError


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


def test_build_extraction_tool_has_name_and_parameters():
    """build_extraction_tool should include function name and parameters."""

    schema = {"type": "object", "properties": {}}
    tool = openai_utils.build_extraction_tool("vacalyser_extract", schema)
    spec = tool[0]
    assert spec["function"]["name"] == "vacalyser_extract"
    assert spec["function"]["parameters"]["type"] == "object"


def test_call_chat_api_passes_reasoning(monkeypatch):
    """Reasoning effort should be forwarded to the API payload."""

    captured: dict[str, Any] = {}

    class _FakeResponse:
        output: list[dict[str, Any]] = []
        output_text = ""
        usage: dict[str, int] = {}

    class _FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _FakeResponse()

    class _FakeClient:
        responses = _FakeResponses()

    monkeypatch.setattr("openai_utils.client", _FakeClient(), raising=False)
    call_chat_api([{"role": "user", "content": "hi"}], reasoning_effort="high")
    assert captured["reasoning"] == {"effort": "high"}


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

    class _FakeProfile:
        def __init__(self, data: dict[str, str]) -> None:
            self._data = data

        def model_dump(self) -> dict[str, str]:
            return self._data

    monkeypatch.setattr(cs, "coerce_and_fill", lambda data: _FakeProfile(data))

    result = extract_with_function("text", {})
    assert result["job_title"] == "Dev"


def test_call_chat_api_executes_tool(monkeypatch):
    """call_chat_api should execute mapped tools and return final content."""

    class _FirstResponse:
        def __init__(self) -> None:
            self.output = [
                {
                    "type": "tool_call",
                    "id": "1",
                    "function": {
                        "name": "get_skill_definition",
                        "arguments": '{"skill": "Python"}',
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
    res = call_chat_api([{"role": "user", "content": "hi"}])
    assert res.content == "done"
    assert res.tool_calls[0]["function"]["name"] == "get_skill_definition"


def _dummy_response(status: int) -> httpx.Response:
    """Return a minimal :class:`httpx.Response` for exception tests."""

    req = httpx.Request("POST", "https://api.openai.com")
    return httpx.Response(status_code=status, request=req)


def test_call_chat_api_authentication_error(monkeypatch):
    """Authentication errors should surface a clear message."""

    class _Resp:
        def create(self, **kwargs):
            raise AuthenticationError("bad key", response=_dummy_response(401), body="")

    class _Client:
        responses = _Resp()

    monkeypatch.setattr("openai_utils.client", _Client(), raising=False)
    with pytest.raises(RuntimeError, match="API key invalid"):
        call_chat_api([{"role": "user", "content": "hi"}])


def test_call_chat_api_rate_limit(monkeypatch):
    """Rate limit errors should surface a clear message."""

    class _Resp:
        def create(self, **kwargs):
            raise RateLimitError("quota", response=_dummy_response(429), body="")

    class _Client:
        responses = _Resp()

    monkeypatch.setattr("openai_utils.client", _Client(), raising=False)
    with pytest.raises(RuntimeError, match="rate limit"):
        call_chat_api([{"role": "user", "content": "hi"}])
