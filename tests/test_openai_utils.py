import json
from copy import deepcopy
import logging
from types import SimpleNamespace
from typing import Any, Callable, Mapping, Sequence

import pytest

import httpx
import openai_utils
import config
from config import ModelTask
from openai_utils import (
    ChatCallResult,
    build_function_tools,
    call_chat_api,
    stream_chat_api,
    extract_with_function,
    model_supports_reasoning,
    model_supports_temperature,
)
from openai_utils.api import (
    ChatPayloadBuilder,
    PayloadContext,
    ResponsesPayloadBuilder,
    build_schema_format_bundle,
)
from openai_utils.client import ResponsesRequest
from llm.cost_router import PromptComplexity, PromptCostEstimate


pytestmark = pytest.mark.integration
from openai import APIError, APITimeoutError, AuthenticationError, BadRequestError, RateLimitError
import streamlit as st

from constants.keys import StateKeys
from llm.rag_pipeline import FieldExtractionContext, RetrievedChunk
from models.need_analysis import NeedAnalysisProfile
from utils.errors import resolve_message


@pytest.fixture(autouse=True)
def reset_model_capability_caches(monkeypatch):
    """Ensure cached model capability flags are cleared between tests."""

    monkeypatch.setattr(openai_utils.api, "_MODELS_WITHOUT_TEMPERATURE", set(), raising=False)
    monkeypatch.setattr(openai_utils.api, "_MODELS_WITHOUT_REASONING", set(), raising=False)
    yield


@pytest.fixture(autouse=True)
def reset_classic_flag():
    """Force Responses API mode unless a test overrides it."""

    previous_mode = config.USE_RESPONSES_API
    config.set_api_mode(True)
    try:
        yield
    finally:
        config.set_api_mode(previous_mode)


@pytest.fixture
def tool_response_event() -> dict[str, Any]:
    """Return a mocked ``response.tool_response`` payload."""

    return {
        "type": "response.tool_response",
        "id": "tool-response-1",
        "call_id": "call-123",
        "output": [
            {
                "type": "text",
                "text": "done",
            }
        ],
    }


@pytest.fixture
def tool_response_object(tool_response_event: Mapping[str, Any]) -> SimpleNamespace:
    """Return a response-like object that exposes the tool response event."""

    return SimpleNamespace(output=[tool_response_event], output_text="", usage={})


def test_call_chat_api_raises_when_no_api_key(monkeypatch):
    """call_chat_api should raise if OpenAI API key is missing."""
    monkeypatch.setattr("openai_utils.api.OPENAI_API_KEY", "")
    monkeypatch.setattr("openai_utils.api.client", None, raising=False)

    with pytest.raises(RuntimeError):
        call_chat_api([{"role": "user", "content": "hi"}])


def test_missing_api_key_triggers_ui_alert_once(monkeypatch):
    """Missing API keys should surface a bilingual UI hint exactly once per session."""

    st.session_state.clear()
    st.session_state["lang"] = "en"

    recorded: list[str] = []

    def _fake_display(msg: str) -> None:
        recorded.append(msg)

    monkeypatch.setattr("openai_utils.api.display_error", _fake_display)
    monkeypatch.setattr("openai_utils.api.OPENAI_API_KEY", "")
    monkeypatch.setattr("openai_utils.api.client", None, raising=False)

    with pytest.raises(RuntimeError):
        call_chat_api([{"role": "user", "content": "hi"}])

    expected_alert = resolve_message(openai_utils.api._MISSING_API_KEY_ALERT_MESSAGE, lang="en")
    assert recorded == [expected_alert]
    assert st.session_state.get(openai_utils.api._MISSING_API_KEY_ALERT_STATE_KEY) is True

    with pytest.raises(RuntimeError):
        call_chat_api([{"role": "user", "content": "hi"}])

    assert recorded == [expected_alert]


def test_call_chat_api_tool_call(monkeypatch):
    """Tool call information should be returned to the caller."""

    class _FakeResponse:
        def __init__(self) -> None:
            self.output: list[dict[str, Any]] = [
                {
                    "type": "response.tool_call",
                    "id": "toolcall_1",
                    "call_id": "call_abc",
                    "function": {
                        "name": "fn",
                        "input": {"job_title": "x"},
                    },
                },
                {
                    "type": "tool_call",
                    "id": "legacy",
                    "name": "legacy_fn",
                    "arguments": '{"foo": "bar"}',
                },
            ]
            self.output_text = ""
            self.usage: dict[str, int] = {}

    class _FakeResponses:
        @staticmethod
        def create(**kwargs):
            return _FakeResponse()

    class _FakeClient:
        responses = _FakeResponses()

    monkeypatch.setattr("openai_utils.api.client", _FakeClient(), raising=False)
    out = call_chat_api(
        [],
        tools=[{"type": "function", "function": {"name": "fn", "parameters": {}}}],
        tool_choice={
            "type": "function",
            "function": {"name": "fn"},
        },
    )
    assert out.tool_calls[0]["call_id"] == "call_abc"
    assert out.tool_calls[0]["function"]["input"] == '{"job_title": "x"}'
    assert out.tool_calls[0]["function"]["arguments"] == '{"job_title": "x"}'
    assert out.tool_calls[1]["call_id"] == "legacy"
    assert out.tool_calls[1]["function"]["arguments"] == '{"foo": "bar"}'


def test_tool_requests_force_classic_payload(monkeypatch):
    """Tool-enabled prompts should route through the classic chat API."""

    monkeypatch.setattr("core.analysis_tools.build_analysis_tools", lambda: ([], {}))

    captured: dict[str, Any] = {}

    def _fake_create(payload: Mapping[str, Any], *, api_mode: str | None = None) -> SimpleNamespace:
        captured["payload"] = dict(payload)
        captured["api_mode"] = api_mode
        return SimpleNamespace(output=[], output_text="", usage={}, id="resp-1")

    monkeypatch.setattr(openai_utils.api, "_create_response_with_timeout", _fake_create)

    call_chat_api(
        [{"role": "user", "content": "hi"}],
        model="gpt-test",
        tools=[{"name": "say_hi", "parameters": {"type": "object"}}],
    )

    sent_payload = captured["payload"]
    assert "messages" in sent_payload
    assert "functions" in sent_payload
    assert "tools" not in sent_payload
    assert captured.get("api_mode") == "chat"


def test_call_chat_api_executes_interview_capacity_tool(monkeypatch):
    """call_chat_api should execute registered analysis tools and relay outputs."""

    from core import analysis_tools

    tool_args = {
        "interviewers": 3,
        "hours_per_week": 4.5,
        "interview_duration_minutes": 45,
        "buffer_minutes": 10,
    }
    original_fn = analysis_tools.calculate_interview_capacity
    expected_payload = original_fn(**tool_args)
    recorded_kwargs: dict[str, Any] = {}

    def _recording_capacity(**kwargs: Any) -> dict[str, Any]:
        recorded_kwargs["kwargs"] = kwargs
        return original_fn(**kwargs)

    monkeypatch.setattr(
        analysis_tools,
        "calculate_interview_capacity",
        _recording_capacity,
        raising=False,
    )

    first_response = SimpleNamespace(
        id="resp-1",
        output=[
            {
                "type": "response.tool_call",
                "id": "call-1",
                "call_id": "call-1",
                "function": {
                    "name": "calculate_interview_capacity",
                    "input": dict(tool_args),
                },
            }
        ],
        output_text="",
        usage={},
    )
    second_response = SimpleNamespace(
        id="resp-2",
        output=[
            {
                "type": "message",
                "content": [
                    {"type": "text", "text": "capacity ready"},
                ],
            }
        ],
        output_text="",
        usage={},
    )

    responses = iter([first_response, second_response])
    recorded_inputs: list[list[dict[str, Any]]] = []

    def _fake_execute_response(payload: dict[str, Any], model: str | None, *, api_mode: str | None = None):
        key = "messages" if "messages" in payload else "input"
        recorded_inputs.append(deepcopy(payload.get(key, [])))
        assert api_mode in {None, "chat"}
        try:
            return next(responses)
        except StopIteration as exc:  # pragma: no cover - defensive
            raise AssertionError("Unexpected additional OpenAI call") from exc

    monkeypatch.setattr(openai_utils.api, "_execute_response", _fake_execute_response, raising=False)
    monkeypatch.setattr(openai_utils.api, "OPENAI_API_KEY", "test-key", raising=False)

    result = call_chat_api(
        [{"role": "user", "content": "Plan our interview schedule"}],
        tool_choice={"type": "function", "function": {"name": "calculate_interview_capacity"}},
    )

    assert recorded_kwargs["kwargs"] == tool_args
    assert len(recorded_inputs) == 2
    tool_message = recorded_inputs[1][-1]
    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "call-1"
    assert json.loads(tool_message["content"]) == expected_payload
    assert result.tool_calls
    assert result.tool_calls[0]["function"]["name"] == "calculate_interview_capacity"
    assert result.content == "capacity ready"


def test_call_chat_api_executes_currency_conversion_tool(monkeypatch):
    """Conversion helper outputs should be injected back into the prompt loop."""

    from core import analysis_tools

    conversion_args = {
        "amount": 100,
        "source_currency": "usd",
        "target_currency": "eur",
    }

    recorded_kwargs: dict[str, Any] = {}
    original_fn = analysis_tools.convert_currency

    def _recording_convert_currency(**kwargs: Any) -> dict[str, Any]:
        recorded_kwargs.update(kwargs)
        return original_fn(**kwargs)

    monkeypatch.setattr(
        analysis_tools,
        "convert_currency",
        _recording_convert_currency,
        raising=False,
    )

    first_response = SimpleNamespace(
        id="resp-1",
        output=[
            {
                "type": "response.tool_call",
                "id": "call-1",
                "call_id": "call-1",
                "function": {
                    "name": "convert_currency",
                    "input": dict(conversion_args),
                },
            }
        ],
        output_text="",
        usage={},
    )

    second_response = SimpleNamespace(
        id="resp-2",
        output=[
            {
                "type": "message",
                "content": [
                    {"type": "text", "text": "conversion done"},
                ],
            }
        ],
        output_text="",
        usage={},
    )

    class _FakeResponses:
        def __init__(self) -> None:
            self._index = 0
            self.captured_turns: list[list[dict[str, Any]]] = []

        def create(self, **kwargs: Any) -> Any:
            key = "messages" if "messages" in kwargs else "input"
            self.captured_turns.append(deepcopy(kwargs.get(key, [])))
            self._index += 1
            return first_response if self._index == 1 else second_response

    fake_responses = _FakeResponses()

    class _FakeClient:
        responses = fake_responses

    monkeypatch.setattr("openai_utils.api.client", _FakeClient(), raising=False)

    result = call_chat_api(
        [{"role": "user", "content": "convert 100 USD to EUR"}],
        tool_choice={"type": "function", "function": {"name": "convert_currency"}},
    )

    assert recorded_kwargs == {
        "amount": 100,
        "source_currency": "usd",
        "target_currency": "eur",
    }
    assert len(fake_responses.captured_turns) == 2
    tool_message = fake_responses.captured_turns[1][-1]
    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "call-1"
    payload = json.loads(tool_message["content"])
    assert payload["success"] is True
    assert payload["source_currency"] == "USD"
    assert payload["target_currency"] == "EUR"
    assert payload["converted_amount"] == pytest.approx(92.17, rel=1e-4)
    assert payload["exchange_rate"] == pytest.approx(0.921659, rel=1e-6)
    assert result.tool_calls[0]["function"]["name"] == "convert_currency"
    assert result.content == "conversion done"


def test_collect_tool_calls_handles_tool_response(
    tool_response_object: SimpleNamespace, tool_response_event: Mapping[str, Any]
):
    """Tool responses should be normalised with serialised output payloads."""

    tool_calls = openai_utils.api._collect_tool_calls(tool_response_object)

    assert len(tool_calls) == 1
    call = tool_calls[0]
    assert call["call_id"] == "call-123"
    assert call["type"] == "response.tool_response"
    expected_payload = json.dumps(tool_response_event["output"])
    assert call["output"] == expected_payload
    assert call["content"] == call["output"]


def test_prepare_payload_classic_mode(monkeypatch):
    """Classic ChatCompletions payloads should use messages/functions schema."""

    config.set_api_mode(False)

    request = openai_utils.api._prepare_payload(
        [{"role": "user", "content": "hello"}],
        model="gpt-4o-mini",
        temperature=0.4,
        max_completion_tokens=256,
        json_schema={"name": "Test", "schema": {"type": "object"}},
        tools=[{"type": "function", "function": {"name": "do", "parameters": {"type": "object"}}}],
        tool_choice={"type": "function", "function": {"name": "do"}},
        tool_functions={"do": lambda **_: None},
        reasoning_effort=None,
        extra={"metadata": {"ignored": True}},
        include_analysis_tools=False,
    )

    payload = request.payload
    assert request.model == "gpt-4o-mini"
    assert payload["messages"][0]["content"] == "hello"
    assert "functions" in payload and payload["functions"][0]["name"] == "do"
    assert payload.get("function_call", {}).get("name") == "do"
    assert "metadata" not in payload
    assert payload.get("max_completion_tokens") == 256
    assert "tool_choice" not in payload
    assert request.tool_specs and request.tool_specs[0]["function"]["name"] == "do"
    assert "input" not in payload
    assert request.tool_functions["do"]


def test_chat_payload_builder_handles_tools_and_schema():
    """Chat payload builder should normalise tools and carry schema hints."""

    schema_bundle = build_schema_format_bundle({"name": "TestPayload", "schema": {"type": "object"}})
    context = PayloadContext(
        messages=[{"role": "user", "content": "hello"}],
        model="gpt-4o-mini",
        temperature=0.3,
        max_completion_tokens=64,
        candidate_models=["gpt-4o-mini"],
        tool_specs=[{"type": "function", "function": {"name": "do", "parameters": {"type": "object"}}}],
        tool_functions={},
        tool_choice={"type": "function", "function": {"name": "do"}},
        schema_bundle=schema_bundle,
        reasoning_effort=None,
        extra=None,
        router_estimate=None,
        previous_response_id=None,
        force_classic_for_tools=True,
        api_mode_override="chat",
    )

    request = ChatPayloadBuilder(context).build()
    payload = request.payload

    assert payload["messages"][0]["content"] == "hello"
    assert payload["functions"][0]["name"] == "do"
    assert payload.get("function_call", {}).get("name") == "do"
    assert payload["max_completion_tokens"] == 64
    assert payload["response_format"]["json_schema"]["name"] == "TestPayload"
    assert request.api_mode_override == "chat"


def test_responses_payload_builder_attaches_router_metadata():
    """Responses payload builder should merge router metadata and extras."""

    schema_bundle = build_schema_format_bundle({"name": "Router", "schema": {"type": "object"}})
    estimate = PromptCostEstimate(total_tokens=10, hard_word_count=2, complexity=PromptComplexity.COMPLEX)
    context = PayloadContext(
        messages=[{"role": "user", "content": "hi"}],
        model="o3-mini",
        temperature=0.5,
        max_completion_tokens=99,
        candidate_models=["o3-mini"],
        tool_specs=[],
        tool_functions={},
        tool_choice=None,
        schema_bundle=schema_bundle,
        reasoning_effort="medium",
        extra={"metadata": {"source": "test-case"}},
        router_estimate=estimate,
        previous_response_id="resp-1",
        force_classic_for_tools=False,
        api_mode_override=None,
    )

    request = ResponsesPayloadBuilder(context).build()
    payload = request.payload

    assert payload["input"][0]["content"] == "hi"
    assert payload["previous_response_id"] == "resp-1"
    assert payload["max_output_tokens"] == 99
    assert payload["reasoning"]["effort"] == "medium"
    assert payload["text"]["format"]["json_schema"]["name"] == "Router"
    assert payload["metadata"]["router"]["tokens"] == 10
    assert payload["metadata"]["router"]["hard_words"] == 2
    assert payload["metadata"]["source"] == "test-case"


def test_call_chat_api_classic_mode(monkeypatch):
    """call_chat_api should normalise ChatCompletions responses."""

    config.set_api_mode(False)

    captured: list[dict[str, Any]] = []

    class _FakeCompletion:
        def __init__(self) -> None:
            self.choices = [
                {
                    "message": {
                        "content": "done",
                    }
                }
            ]
            self.usage = {"prompt_tokens": 3, "completion_tokens": 5}
            self.id = "chat-123"

    def _fake_create(payload: Mapping[str, Any], *, api_mode: str | None = None) -> Any:
        captured.append(dict(payload))
        return _FakeCompletion()

    monkeypatch.setattr(openai_utils.api, "_create_response_with_timeout", _fake_create)

    result = call_chat_api([{"role": "user", "content": "hi"}])

    assert captured and "messages" in captured[0]
    assert result.content == "done"
    assert result.response_id == "chat-123"
    assert result.usage["input_tokens"] == 3
    assert result.usage["output_tokens"] == 5


def test_stream_chat_api_classic_mode(monkeypatch):
    """Streaming should consume ChatCompletions events."""

    config.set_api_mode(False)

    events = [
        {"type": "content.delta", "delta": "Hel"},
        {"type": "content.delta", "delta": "lo"},
    ]

    final_response = {
        "choices": [{"message": {"content": "Hello"}}],
        "usage": {"prompt_tokens": 2, "completion_tokens": 3},
        "id": "chat-stream",
    }

    class _FakeStream:
        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

        def __iter__(self):
            return iter(events)

        def get_final_completion(self):
            return final_response

    class _FakeClient:
        class _Chat:
            class _Completions:
                @staticmethod
                def stream(**kwargs):
                    return _FakeStream()

            completions = _Completions()

        chat = _Chat()

    monkeypatch.setattr(openai_utils.api, "client", _FakeClient(), raising=False)

    stream = stream_chat_api([{"role": "user", "content": "hi"}])
    chunks = list(stream)

    assert "".join(chunks) == "Hello"
    result = stream.result
    assert result.content == "Hello"
    assert result.usage["input_tokens"] == 2
    assert result.usage["output_tokens"] == 3
    assert result.response_id == "chat-stream"


def test_tool_loop_sets_previous_response_id(monkeypatch):
    """Tool execution loops should reuse the Responses session."""

    calls: list[dict[str, Any]] = []

    class _ToolResponse:
        def __init__(self) -> None:
            self.output = [
                {
                    "type": "response.tool_call",
                    "id": "tool-call",
                    "call_id": "tool-call",
                    "function": {
                        "name": "fn",
                        "arguments": json.dumps({"value": 1}),
                    },
                }
            ]
            self.output_text = ""
            self.usage = {"input_tokens": 3}
            self.id = "resp-1"

    class _FinalResponse:
        def __init__(self) -> None:
            self.output = []
            self.output_text = "done"
            self.usage = {"output_tokens": 5}
            self.id = "resp-2"

    class _FakeResponses:
        def __init__(self) -> None:
            self._index = 0

        def create(self, **kwargs: Any) -> Any:
            calls.append(dict(kwargs))
            self._index += 1
            return _ToolResponse() if self._index == 1 else _FinalResponse()

    class _FakeClient:
        responses = _FakeResponses()

    monkeypatch.setattr("openai_utils.api.client", _FakeClient(), raising=False)

    tool_payload: dict[str, Any] = {}

    def _tool_fn(value: int | None = None) -> dict[str, Any]:
        tool_payload["value"] = value
        return {"ok": True}

    result = call_chat_api(
        [{"role": "user", "content": "hi"}],
        tools=[{"type": "function", "function": {"name": "fn", "parameters": {}}}],
        tool_choice={"type": "function", "function": {"name": "fn"}},
        tool_functions={"fn": _tool_fn},
    )

    assert tool_payload == {"value": 1}
    assert len(calls) == 2
    assert "previous_response_id" not in calls[0]
    assert calls[1]["previous_response_id"] == "resp-1"
    assert result.content == "done"
    assert result.response_id == "resp-2"


def test_tool_response_replayed_between_turns(monkeypatch, tool_response_event):
    """Tool responses emitted by the API should be replayed into the next turn."""

    st.session_state.clear()

    expected_payload = json.dumps(tool_response_event["output"])
    calls: list[list[dict[str, Any]]] = []

    class _ToolResponse:
        def __init__(self) -> None:
            self.output = [tool_response_event]
            self.output_text = ""
            self.usage = {"input_tokens": 1}
            self.id = "resp-tool"

    class _FinalResponse:
        def __init__(self) -> None:
            self.output = []
            self.output_text = "assistant"
            self.usage = {"output_tokens": 2}
            self.id = "resp-final"

    class _FakeResponses:
        def __init__(self) -> None:
            self._index = 0

        def create(self, **kwargs: Any) -> Any:
            key = "messages" if "messages" in kwargs else "input"
            calls.append(deepcopy(kwargs.get(key, [])))
            self._index += 1
            return _ToolResponse() if self._index == 1 else _FinalResponse()

    class _FakeClient:
        responses = _FakeResponses()

    monkeypatch.setattr("openai_utils.api.client", _FakeClient(), raising=False)

    result = call_chat_api([{"role": "user", "content": "hi"}])

    assert len(calls) == 2
    assert calls[1][-1] == {
        "role": "tool",
        "tool_call_id": tool_response_event["call_id"],
        "content": expected_payload,
    }
    assert result.tool_calls[0]["type"] == "response.tool_response"
    assert result.tool_calls[0]["output"] == expected_payload
    assert result.content == "assistant"


def test_call_chat_api_propagates_bad_request_without_retry(monkeypatch):
    """Bad request errors should be raised immediately without retries."""

    calls: list[dict[str, Any]] = []

    def _raise_bad_request(payload: Mapping[str, Any], *, api_mode: str | None = None) -> None:
        calls.append(dict(payload))
        request = httpx.Request("POST", "https://api.openai.com/v1/responses")
        response = httpx.Response(
            status_code=400,
            request=request,
            json={"error": {"message": "invalid"}},
        )
        raise BadRequestError("invalid", response=response, body={"error": {"message": "invalid"}})

    monkeypatch.setattr(openai_utils.api, "_create_response_with_timeout", _raise_bad_request)

    with pytest.raises(BadRequestError):
        call_chat_api([{"role": "user", "content": "hi"}])

    assert len(calls) == 1


def test_call_chat_api_gives_up_on_invalid_schema(monkeypatch):
    """Schema validation errors should abort retries to avoid API spam."""

    attempts = 0

    def _raise_schema_error(payload: Mapping[str, Any], *, api_mode: str | None = None) -> None:
        nonlocal attempts
        attempts += 1
        request = httpx.Request("POST", "https://api.openai.com/v1/responses")
        response = httpx.Response(
            status_code=400,
            request=request,
            json={"error": {"message": "invalid_json_schema", "code": "invalid_json_schema"}},
        )
        raise APIError("invalid_json_schema", response=response, body=response.json())

    monkeypatch.setattr(openai_utils.api, "_create_response_with_timeout", _raise_schema_error)

    with pytest.raises(APIError):
        call_chat_api(
            [
                {"role": "user", "content": "hi"},
            ],
            json_schema={"name": "Profile", "schema": {"type": "object"}},
        )

    assert attempts == 1


def test_call_chat_api_retries_transient_timeout(monkeypatch):
    """Transient timeout errors should trigger a retry before succeeding."""

    attempts = 0

    def _maybe_timeout(payload: Mapping[str, Any], *, api_mode: str | None = None) -> Any:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            request = httpx.Request("POST", "https://api.openai.com/v1/responses")
            raise APITimeoutError(request)
        return type(
            "_FakeResponse",
            (),
            {"output": [], "output_text": "assistant", "usage": {}, "id": "resp-success"},
        )()

    monkeypatch.setattr(openai_utils.api, "_create_response_with_timeout", _maybe_timeout)

    result = call_chat_api([{"role": "user", "content": "hi"}])

    assert attempts == 2
    assert result.content == "assistant"


def test_call_chat_api_returns_output_json(monkeypatch):
    """Responses output JSON should be serialised into the content payload."""

    payload = {"suggestions": ["A", "B"]}

    class _FakeResponse:
        def __init__(self) -> None:
            self.output = [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "output_json",
                            "json": payload,
                        }
                    ],
                }
            ]
            self.output_text = ""
            self.usage: dict[str, int] = {}
            self.id = "resp-output-json"

    class _FakeResponses:
        @staticmethod
        def create(**kwargs):
            return _FakeResponse()

    class _FakeClient:
        responses = _FakeResponses()

    monkeypatch.setattr("openai_utils.api.client", _FakeClient(), raising=False)
    result = call_chat_api([{"role": "user", "content": "hi"}])

    assert result.content == json.dumps(payload)
    assert result.response_id == "resp-output-json"


def test_call_chat_api_dual_prompt_returns_comparison(monkeypatch):
    """Dual prompt evaluations should capture both outputs and metadata."""

    st.session_state.clear()
    st.session_state[StateKeys.USAGE] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "by_task": {},
    }

    class _FakeResponse:
        def __init__(self, text: str, usage: Mapping[str, int], identifier: str):
            self.output_text = text
            self.output: list[dict[str, Any]] = []
            self.usage = usage
            self.id = identifier

    responses = [
        _FakeResponse("Primary", {"input_tokens": 1, "output_tokens": 2}, "resp-primary"),
        _FakeResponse("Secondary", {"input_tokens": 2, "output_tokens": 3}, "resp-secondary"),
    ]

    def _fake_prepare(messages: Sequence[dict[str, Any]], **_: Any) -> ResponsesRequest:
        return ResponsesRequest(
            payload={"model": "test", "input": list(messages)},
            model="test",
            tool_specs=[],
            tool_functions={},
            candidate_models=["test"],
        )

    def _fake_execute(_: Mapping[str, Any], __: str | None, *, api_mode: str | None = None):
        return responses.pop(0)

    monkeypatch.setattr(openai_utils.api, "_prepare_payload", _fake_prepare)
    monkeypatch.setattr(openai_utils.api, "_execute_response", _fake_execute)

    result = call_chat_api(
        [{"role": "user", "content": "hi"}],
        comparison_messages=[{"role": "user", "content": "hello"}],
        comparison_label="A/B",
        comparison_options={"dispatch": "sequential"},
    )

    assert result.content == "Primary"
    assert result.secondary_content == "Secondary"
    assert result.usage["input_tokens"] == 3
    assert result.usage["output_tokens"] == 5
    assert result.secondary_usage == {"input_tokens": 2, "output_tokens": 3}
    assert result.comparison is not None
    assert result.comparison["label"] == "A/B"
    assert result.comparison["secondary"]["content"] == "Secondary"
    assert result.comparison["diff"]["are_equal"] is False
    assert result.response_id == "resp-primary"
    assert result.secondary_response_id == "resp-secondary"


def test_call_chat_api_dual_prompt_custom_metadata(monkeypatch):
    """Custom comparison metadata builders should feed into the result."""

    primary = ChatCallResult("A", [], {"input_tokens": 1}, response_id="primary-id")
    secondary = ChatCallResult("Beta", [], {"input_tokens": 4}, response_id="secondary-id")

    calls: list[dict[str, Any]] = []

    def _fake_single(
        messages: Sequence[dict[str, Any]],
        *,
        model: str | None = None,
        temperature: float | None = 0.2,
        max_completion_tokens: int | None = None,
        json_schema: Mapping[str, Any] | None = None,
        tools: Sequence[dict[str, Any]] | None = None,
        tool_choice: Any | None = None,
        tool_functions: Mapping[str, Any] | None = None,
        reasoning_effort: str | None = None,
        verbosity: str | None = None,
        extra: Mapping[str, Any] | None = None,
        task: Any | None = None,
        include_raw_response: bool = False,
        capture_file_search: bool = False,
        previous_response_id: str | None = None,
    ) -> ChatCallResult:
        calls.append(
            {
                "messages": messages,
                "model": model,
                "temperature": temperature,
                "max_completion_tokens": max_completion_tokens,
                "json_schema": json_schema,
                "tools": tools,
                "tool_choice": tool_choice,
                "tool_functions": tool_functions,
                "reasoning_effort": reasoning_effort,
                "verbosity": verbosity,
                "extra": extra,
                "task": task,
                "include_raw_response": include_raw_response,
                "capture_file_search": capture_file_search,
                "previous_response_id": previous_response_id,
            }
        )
        return primary if len(calls) == 1 else secondary

    monkeypatch.setattr(openai_utils.api, "_call_chat_api_single", _fake_single)

    def _builder(first: ChatCallResult, second: ChatCallResult) -> Mapping[str, Any]:
        return {"winner": "secondary" if len(second.content or "") > len(first.content or "") else "primary"}

    result = call_chat_api(
        [{"role": "user", "content": "hi"}],
        comparison_messages=[{"role": "user", "content": "hey"}],
        comparison_options={
            "dispatch": "sequential",
            "metadata_builder": _builder,
            "temperature": 0.75,
        },
    )

    assert result.comparison is not None
    assert result.comparison["custom"] == {"winner": "secondary"}
    assert calls[0]["temperature"] == 0.2
    assert calls[1]["temperature"] == 0.75
    assert result.response_id == "primary-id"
    assert result.secondary_response_id == "secondary-id"


def test_call_chat_api_sets_json_schema_text_format(monkeypatch):
    """Structured calls should configure the JSON schema text format."""

    captured: dict[str, Any] = {}

    class _FakeResponse:
        output: list[dict[str, Any]] = []
        output_text = ""
        usage: dict[str, int] = {}

    class _FakeResponses:
        def create(self, **kwargs: Any) -> _FakeResponse:
            captured.update(kwargs)
            return _FakeResponse()

    class _FakeClient:
        def __init__(self) -> None:
            self.responses = _FakeResponses()

    fake_client = _FakeClient()
    monkeypatch.setattr(openai_utils.api, "client", fake_client, raising=False)
    monkeypatch.setattr(openai_utils.api, "get_client", lambda: fake_client)

    schema = {"name": "vacancy", "schema": {"type": "object", "properties": {}}}

    call_chat_api(
        [{"role": "user", "content": "hi"}],
        json_schema=schema,
    )

    format_block = captured["text"]["format"]
    assert format_block["type"] == "json_schema"
    assert "type" not in captured["text"]
    schema_block = format_block["json_schema"]
    assert schema_block["name"] == schema["name"]
    assert schema_block["schema"] == schema["schema"]
    assert schema_block["strict"] is True


def test_convert_responses_payload_to_chat_keeps_schema_name() -> None:
    """Fallback conversion should preserve the JSON schema bundle."""

    schema_bundle = openai_utils.api.build_schema_format_bundle(
        {
            "name": "fallback_schema",
            "schema": {"type": "object"},
        }
    )

    payload = {
        "model": "gpt-4o-mini",
        "input": [{"role": "user", "content": "hi"}],
        "text": {"format": deepcopy(schema_bundle.responses_format)},
    }

    chat_payload = openai_utils.api._convert_responses_payload_to_chat(payload)

    response_format = chat_payload.get("response_format", {})
    assert response_format.get("type") == "json_schema"
    json_schema_block = response_format.get("json_schema", {})
    assert json_schema_block["name"] == "fallback_schema"
    assert json_schema_block["schema"] == {"type": "object"}


def test_stream_chat_api_yields_chunks(monkeypatch):
    """Streaming helper should yield incremental text and capture usage."""

    st.session_state.clear()
    st.session_state[StateKeys.USAGE] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "by_task": {},
    }

    class _FakeFinalResponse:
        output_text = "Hello world"
        output: list[dict[str, Any]] = []
        usage = {"input_tokens": 1, "output_tokens": 4}
        id = "stream-1"

    class _FakeStream:
        def __init__(self) -> None:
            self._events = [
                SimpleNamespace(type="response.output_text.delta", delta="Hello "),
                SimpleNamespace(type="response.output_text.delta", delta="world"),
            ]

        def __iter__(self):
            return iter(self._events)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get_final_response(self):
            return _FakeFinalResponse()

    class _FakeResponses:
        def __init__(self) -> None:
            self.called = False
            self.kwargs: dict[str, Any] = {}

        def stream(self, **kwargs: Any):
            self.called = True
            self.kwargs = kwargs
            return _FakeStream()

    fake_responses = _FakeResponses()

    class _FakeClient:
        responses = fake_responses

    monkeypatch.setattr("openai_utils.api.client", _FakeClient(), raising=False)

    stream = stream_chat_api(
        [{"role": "user", "content": "hello"}],
        model=config.REASONING_MODEL,
        task=ModelTask.JOB_AD,
    )

    chunks = list(stream)
    assert chunks == ["Hello ", "world"]
    assert stream.text == "Hello world"

    final = stream.result
    assert final.content == "Hello world"
    assert final.response_id == "stream-1"
    assert st.session_state[StateKeys.USAGE]["output_tokens"] == 4
    assert st.session_state[StateKeys.USAGE]["by_task"][ModelTask.JOB_AD.value]["output"] == 4
    assert fake_responses.called


def test_call_chat_api_records_task_usage(monkeypatch):
    """Token counters should aggregate totals per task identifier."""

    st.session_state.clear()
    st.session_state[StateKeys.USAGE] = {
        "input_tokens": 0,
        "output_tokens": 0,
        "by_task": {},
    }

    class _FakeResponse:
        def __init__(self) -> None:
            self.output: list[dict[str, Any]] = []
            self.output_text = "Done"
            self.usage = {"input_tokens": 2, "output_tokens": 5}

    class _FakeResponses:
        @staticmethod
        def create(**kwargs: Any):
            return _FakeResponse()

    class _FakeClient:
        responses = _FakeResponses()

    monkeypatch.setattr("openai_utils.api.client", _FakeClient(), raising=False)

    result = call_chat_api(
        [{"role": "user", "content": "Hi"}],
        task=ModelTask.INTERVIEW_GUIDE,
    )

    assert result.content == "Done"
    usage_state = st.session_state[StateKeys.USAGE]
    assert usage_state["input_tokens"] == 2
    assert usage_state["output_tokens"] == 5
    assert usage_state["by_task"][ModelTask.INTERVIEW_GUIDE.value] == {
        "input": 2,
        "output": 5,
    }


def test_call_chat_api_handles_nested_usage(monkeypatch):
    """Existing usage counters stored as mappings should not break aggregation."""

    st.session_state.clear()
    st.session_state[StateKeys.USAGE] = {
        "input_tokens": {"total": 10},
        "output_tokens": {"total": 20},
        "by_task": {
            ModelTask.EXTRACTION.value: {
                "input": {"total": 4},
                "output": {"total": 6},
            }
        },
    }

    class _FakeResponse:
        def __init__(self) -> None:
            self.output: list[dict[str, Any]] = []
            self.output_text = "Done"
            self.usage = {
                "input_tokens": {"text": 3, "cached": 0, "total": 3},
                "output_tokens": {"text": 2, "cached": 0, "total": 2},
            }

    class _FakeResponses:
        @staticmethod
        def create(**kwargs: Any):
            return _FakeResponse()

    class _FakeClient:
        responses = _FakeResponses()

    monkeypatch.setattr("openai_utils.api.client", _FakeClient(), raising=False)

    result = call_chat_api(
        [{"role": "user", "content": "Hi"}],
        task=ModelTask.EXTRACTION,
    )

    assert result.content == "Done"
    usage_state = st.session_state[StateKeys.USAGE]
    assert usage_state["input_tokens"] == 13
    assert usage_state["output_tokens"] == 22
    assert usage_state["by_task"][ModelTask.EXTRACTION.value] == {
        "input": 7,
        "output": 8,
    }


def test_call_chat_api_normalises_tool_schema(monkeypatch):
    """Function tools should expose nested metadata while built-ins expose names."""

    captured: dict[str, Any] = {}

    class _FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            for tool in kwargs.get("tools", []):
                if tool.get("type") == "function":
                    fn_block = tool.get("function", {})
                    assert "name" in fn_block and fn_block["name"]
                    assert "parameters" in fn_block
                    assert tool.get("name") == fn_block["name"]
                else:
                    assert "function" not in tool
                    assert tool.get("name") in {None, tool.get("type")}
            return type("R", (), {"output": [], "output_text": "", "usage": {}})()

    class _FakeClient:
        responses = _FakeResponses()

    monkeypatch.setattr("openai_utils.api.client", _FakeClient(), raising=False)
    call_chat_api(
        [],
        tools=[{"type": "function", "function": {"name": "fn", "parameters": {}}}],
    )

    assert any(tool.get("type") == "web_search" for tool in captured.get("tools", []))


def test_prepare_payload_includes_analysis_helpers():
    """Base payload should expose web search and analysis helper tools."""

    request = openai_utils.api._prepare_payload(
        messages=[{"role": "user", "content": "hi"}],
        model=config.REASONING_MODEL,
        temperature=None,
        max_completion_tokens=None,
        json_schema=None,
        tools=[{"type": "function", "function": {"name": "custom", "parameters": {}}}],
        tool_choice=None,
        tool_functions={},
        reasoning_effort=None,
        extra=None,
        include_analysis_tools=True,
    )

    payload = request.payload
    tool_map = request.tool_functions
    tool_types = {tool.get("type") for tool in payload.get("tools", [])}
    assert "web_search" in tool_types
    assert "web_search_preview" in tool_types

    function_names = {
        tool.get("function", {}).get("name") for tool in payload.get("tools", []) if tool.get("type") == "function"
    }
    assert "convert_currency" in function_names
    assert "normalise_date" in function_names
    assert callable(tool_map["convert_currency"])
    assert callable(tool_map["normalise_date"])

    for tool in payload["tools"]:
        if tool.get("type") == "function":
            fn_payload = tool.get("function", {})
            assert fn_payload.get("name")
            assert tool.get("name") == fn_payload.get("name")
        else:
            assert tool.get("name") in {None, tool.get("type")}


def test_prepare_payload_normalises_legacy_tool_choice():
    """Legacy function tool choices should be translated to the nested schema."""

    request = openai_utils.api._prepare_payload(
        messages=[{"role": "user", "content": "hi"}],
        model=config.REASONING_MODEL,
        temperature=None,
        max_completion_tokens=None,
        json_schema=None,
        tools=[{"type": "function", "function": {"name": "fn", "parameters": {}}}],
        tool_choice={
            "type": "function",
            "name": "fn",
            "arguments": "{}",
            "reasoning": {"steps": 1},
        },
        tool_functions={"fn": lambda: None},
        reasoning_effort=None,
        extra=None,
        include_analysis_tools=False,
    )

    payload = request.payload
    tool_choice = payload.get("tool_choice")
    assert isinstance(tool_choice, dict)
    assert tool_choice.get("type") == "function"
    assert "name" not in tool_choice

    fn_payload = tool_choice.get("function")
    assert isinstance(fn_payload, dict)
    assert fn_payload["name"] == "fn"
    assert fn_payload["arguments"] == "{}"
    assert fn_payload["reasoning"] == {"steps": 1}


def test_build_extraction_tool_has_name_and_parameters():
    """build_extraction_tool should include function name and parameters."""

    schema = {"type": "object", "properties": {}}
    tool = openai_utils.build_extraction_tool("NeedAnalysisProfile", schema)
    spec = tool[0]
    assert spec["name"] == "NeedAnalysisProfile"
    assert spec["parameters"]["type"] == "object"
    assert spec["parameters"]["additionalProperties"] is False


def test_build_extraction_tool_auto_describes_schema_fields() -> None:
    """Automatically generated description should mention key schema fields."""

    schema = {
        "type": "object",
        "properties": {
            "requirements": {
                "type": "object",
                "properties": {
                    "hard_skills_required": {"type": "array", "items": {"type": "string"}},
                    "soft_skills_required": {"type": "array", "items": {"type": "string"}},
                    "languages_required": {"type": "array", "items": {"type": "string"}},
                },
            },
            "role_summary": {"type": "string"},
        },
    }

    tool = openai_utils.build_extraction_tool("extract", schema)
    description = tool[0]["description"]

    assert "requirements.hard_skills_required" in description
    assert "requirements.soft_skills_required" in description
    assert "requirements.languages_required" in description


def test_build_extraction_tool_allows_custom_description() -> None:
    """Callers can provide a tailored description for the tool."""

    schema = {"type": "object", "properties": {"salary": {"type": "string"}}}
    custom_description = "Estimate annual salary bands for the vacancy."

    tool = openai_utils.build_extraction_tool("salary", schema, description=custom_description)
    assert tool[0]["description"] == custom_description


def test_build_function_tools_normalises_specs() -> None:
    """Helper should inject tool names and copy parameters."""

    def _impl(skill: str) -> dict[str, str]:  # pragma: no cover - invoked in helper mapping
        return {"definition": skill}

    parameters = {"type": "object", "properties": {"skill": {"type": "string"}}}
    specs = {
        "describe_skill": {
            "description": "Return a definition for the provided skill.",
            "parameters": parameters,
            "callable": _impl,
        }
    }

    tools, funcs = build_function_tools(specs)
    assert len(tools) == 1
    spec = tools[0]
    assert spec["name"] == "describe_skill"
    assert spec["description"] == specs["describe_skill"]["description"]
    assert spec["parameters"] == parameters
    assert spec["parameters"] is not parameters
    assert funcs["describe_skill"] is _impl


def test_build_extraction_tool_marks_required_recursively() -> None:
    """Nested objects should receive required arrays and nullable types."""

    schema = {
        "type": "object",
        "properties": {
            "outer": {
                "type": "object",
                "properties": {"inner": {"type": "string"}},
            }
        },
    }
    tool = openai_utils.build_extraction_tool("extract", schema)
    params = tool[0]["parameters"]
    assert params["required"] == ["outer"]
    outer = params["properties"]["outer"]
    assert outer["required"] == ["inner"]
    assert outer["properties"]["inner"]["type"] == ["string", "null"]


def test_build_extraction_tool_can_relax_required_fields() -> None:
    """Callers may opt-out of auto-marking every property as required."""

    schema = {
        "type": "object",
        "properties": {
            "outer": {
                "type": "object",
                "properties": {
                    "inner": {"type": "string"},
                    "optional": {"type": "integer"},
                },
            }
        },
    }

    tool = openai_utils.build_extraction_tool("extract", schema, require_all_fields=False)
    params = tool[0]["parameters"]
    assert "required" not in params
    outer = params["properties"]["outer"]
    assert "required" not in outer
    assert outer["properties"]["inner"]["type"] == ["string", "null"]


def test_call_chat_api_includes_reasoning_for_supported_models(monkeypatch):
    """Reasoning effort should be forwarded when the model accepts it."""

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

    monkeypatch.setattr("openai_utils.api.client", _FakeClient(), raising=False)
    call_chat_api(
        [{"role": "user", "content": "hi"}],
        model="o1-mini",
        reasoning_effort="high",
    )
    assert captured["reasoning"] == {"effort": "high"}


def test_call_chat_api_uses_session_reasoning_default(monkeypatch):
    """Reasoning payload should honour the session's stored effort level."""

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

    st.session_state.clear()
    st.session_state[StateKeys.REASONING_EFFORT] = "minimal"

    monkeypatch.setattr("openai_utils.api.client", _FakeClient(), raising=False)
    call_chat_api(
        [{"role": "user", "content": "hi"}],
        model="o1-mini",
    )
    assert captured["reasoning"] == {"effort": "minimal"}


def test_call_chat_api_omits_reasoning_for_standard_models(monkeypatch):
    """Regular chat models should not receive the reasoning parameter."""

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

    monkeypatch.setattr("openai_utils.api.client", _FakeClient(), raising=False)
    call_chat_api(
        [{"role": "user", "content": "hi"}],
        model=config.LIGHTWEIGHT_MODEL,
        reasoning_effort="high",
    )
    assert "reasoning" not in captured


def test_call_chat_api_includes_explicit_verbosity_hint(monkeypatch):
    """Explicit verbosity settings should be translated into system hints."""

    captured: dict[str, Any] = {}

    class _FakeResponse:
        output: list[dict[str, Any]] = []
        output_text = "hi"
        usage: dict[str, int] = {}

    class _FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _FakeResponse()

    class _FakeClient:
        responses = _FakeResponses()

    monkeypatch.setattr("openai_utils.api.client", _FakeClient(), raising=False)
    call_chat_api(
        [{"role": "user", "content": "hi"}],
        verbosity="high",
    )
    assert "verbosity" not in captured
    system_message = captured["input"][0]
    assert system_message["role"] == "system"
    content = system_message["content"]
    assert "Antwort-Detailgrad" in content
    assert "ausführliche" in content or "thorough" in content


def test_call_chat_api_uses_session_verbosity_default(monkeypatch):
    """When omitted the helper should fall back to the session verbosity hint."""

    captured: dict[str, Any] = {}

    class _FakeResponse:
        output: list[dict[str, Any]] = []
        output_text = "hi"
        usage: dict[str, int] = {}

    class _FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _FakeResponse()

    class _FakeClient:
        responses = _FakeResponses()

    st.session_state.clear()
    st.session_state["verbosity"] = "low"

    monkeypatch.setattr("openai_utils.api.client", _FakeClient(), raising=False)
    call_chat_api(
        [{"role": "user", "content": "hi"}],
    )
    assert "verbosity" not in captured
    system_message = captured["input"][0]
    assert system_message["role"] == "system"
    content = system_message["content"]
    assert "Antwort-Detailgrad" in content
    assert "kurz" in content or "concise" in content


def test_call_chat_api_skips_temperature_for_reasoning_model(monkeypatch):
    """Reasoning models should not receive an unsupported temperature parameter."""

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

    monkeypatch.setattr("openai_utils.api.client", _FakeClient(), raising=False)
    call_chat_api(
        [{"role": "user", "content": "hi"}],
        model="o1-mini",
        temperature=0.7,
    )
    assert "temperature" not in captured


def test_suggest_onboarding_plans_uses_json_payload(monkeypatch):
    """Onboarding helper should parse JSON schema responses into suggestions."""

    expected = ["Kickoff", "Buddy intro", "Training", "Team lunch", "Retro"]

    def _fake_call(messages, **kwargs):  # noqa: ANN001 - signature controlled by API helper
        return ChatCallResult(json.dumps({"suggestions": expected}), [], {})

    monkeypatch.setattr("openai_utils.extraction.api.call_chat_api", _fake_call, raising=False)

    suggestions = openai_utils.extraction.suggest_onboarding_plans("Data Scientist", model="dummy-model")

    assert suggestions == expected


def test_call_chat_api_retries_without_temperature(monkeypatch):
    """The client should retry without temperature when the model rejects it."""

    class _FakeBadRequestError(Exception):
        def __init__(
            self,
            message: str,
            *,
            error_payload: Mapping[str, Any] | None = None,
            body: Mapping[str, Any] | None = None,
        ) -> None:
            super().__init__(message)
            self.message = message
            if error_payload is not None:
                self.error = error_payload
            if body is not None:
                self.body = body

    monkeypatch.setattr("openai_utils.api.BadRequestError", _FakeBadRequestError)

    scenarios: list[tuple[str, Callable[[], Exception], str]] = [
        (
            "legacy-message",
            lambda: _FakeBadRequestError("Unsupported parameter: 'temperature' is not supported with this model."),
            "gpt-legacy-temp",
        ),
        (
            "structured-error-attr",
            lambda: _FakeBadRequestError(
                "Request invalid for this model.",
                error_payload={
                    "code": "unsupported_parameter",
                    "param": "temperature",
                    "message": "Parameter `temperature` is not supported for this model.",
                },
            ),
            "gpt-structured-temp",
        ),
        (
            "structured-body",
            lambda: _FakeBadRequestError(
                "Bad request",
                body={
                    "error": {
                        "code": "unsupported_parameter",
                        "message": "The model gpt-o1-preview does not support temperature.",
                    }
                },
            ),
            "gpt-body-temp",
        ),
    ]

    final_calls: list[dict[str, Any]] | None = None
    final_model: str | None = None

    for _, error_factory, model_name in scenarios:
        calls: list[dict[str, Any]] = []

        class _FakeResponses:
            def __init__(self) -> None:
                self._call_count = 0

            def create(self, **kwargs):
                self._call_count += 1
                calls.append(dict(kwargs))
                if self._call_count == 1:
                    raise error_factory()
                return SimpleNamespace(output=[], output_text="", usage={})

        class _FakeClient:
            def __init__(self) -> None:
                self.responses = _FakeResponses()

        monkeypatch.setattr("openai_utils.api.client", _FakeClient(), raising=False)

        result = call_chat_api(
            [{"role": "user", "content": "hi"}],
            model=model_name,
            temperature=0.5,
        )

        assert len(calls) == 2
        assert "temperature" in calls[0]
        assert "temperature" not in calls[1]
        assert result.tool_calls == []
        assert not model_supports_temperature(model_name)

        final_calls = calls
        final_model = model_name

    assert final_calls is not None and final_model is not None
    final_calls.clear()

    call_chat_api(
        [{"role": "user", "content": "hi again"}],
        model=final_model,
        temperature=0.3,
    )

    assert len(final_calls) == 1
    assert "temperature" not in final_calls[0]


def test_call_chat_api_retries_without_reasoning(monkeypatch):
    """The client should retry without reasoning when the model rejects it."""

    class _FakeBadRequestError(Exception):
        def __init__(
            self,
            message: str,
            *,
            error_payload: Mapping[str, Any] | None = None,
            body: Mapping[str, Any] | None = None,
        ) -> None:
            super().__init__(message)
            self.message = message
            if error_payload is not None:
                self.error = error_payload
            if body is not None:
                self.body = body

    monkeypatch.setattr("openai_utils.api.BadRequestError", _FakeBadRequestError)

    scenarios: list[tuple[str, Callable[[], Exception], str]] = [
        (
            "legacy-message",
            lambda: _FakeBadRequestError("Unsupported parameter: 'reasoning' is not supported for this model."),
            "gpt-legacy-reasoning",
        ),
        (
            "structured-error-attr",
            lambda: _FakeBadRequestError(
                "Request invalid for this model.",
                error_payload={
                    "code": "unsupported_parameter",
                    "param": "reasoning",
                    "message": "Parameter `reasoning` cannot be used with this model.",
                },
            ),
            "gpt-structured-reasoning",
        ),
        (
            "structured-body",
            lambda: _FakeBadRequestError(
                "Bad request",
                body={
                    "error": {
                        "code": "unsupported_parameter",
                        "message": "The model gpt-o1-preview does not support reasoning options.",
                    }
                },
            ),
            "gpt-body-reasoning",
        ),
    ]

    final_calls: list[dict[str, Any]] | None = None
    final_model: str | None = None

    for _, error_factory, model_name in scenarios:
        calls: list[dict[str, Any]] = []

        class _FakeResponses:
            def __init__(self) -> None:
                self._call_count = 0

            def create(self, **kwargs):
                self._call_count += 1
                calls.append(dict(kwargs))
                if self._call_count == 1:
                    raise error_factory()
                return SimpleNamespace(output=[], output_text="", usage={})

        class _FakeClient:
            def __init__(self) -> None:
                self.responses = _FakeResponses()

        monkeypatch.setattr("openai_utils.api.client", _FakeClient(), raising=False)

        result = call_chat_api(
            [{"role": "user", "content": "hi"}],
            model=model_name,
            reasoning_effort="medium",
        )

        assert len(calls) == 2
        assert "reasoning" in calls[0]
        assert "reasoning" not in calls[1]
        assert result.tool_calls == []
        assert not model_supports_reasoning(model_name)

        final_calls = calls
        final_model = model_name

    assert final_calls is not None and final_model is not None
    final_calls.clear()

    call_chat_api(
        [{"role": "user", "content": "hi again"}],
        model=final_model,
        reasoning_effort="medium",
    )

    assert len(final_calls) == 1
    assert "reasoning" not in final_calls[0]


def test_call_chat_api_handles_openai_bad_request_without_reasoning(monkeypatch):
    """A real BadRequestError should trigger a retry without the reasoning payload."""

    calls: list[dict[str, Any]] = []

    class _FakeResponses:
        def __init__(self) -> None:
            self._call_count = 0

        def create(self, **kwargs: Any):
            self._call_count += 1
            calls.append(dict(kwargs))
            if self._call_count == 1:
                request = httpx.Request("POST", "https://api.openai.com/v1/responses")
                response = httpx.Response(
                    status_code=400,
                    json={"error": {"message": "unsupported parameter: reasoning"}},
                    request=request,
                )
                raise BadRequestError(
                    "unsupported parameter: reasoning",
                    response=response,
                    body={"error": {"message": "unsupported parameter: reasoning"}},
                )
            return SimpleNamespace(output=[], output_text="", usage={})

    class _FakeClient:
        responses = _FakeResponses()

    monkeypatch.setattr("openai_utils.api.client", _FakeClient(), raising=False)

    call_chat_api(
        [{"role": "user", "content": "hi"}],
        model="o1-mini",
        reasoning_effort="medium",
    )

    assert len(calls) == 2
    assert "reasoning" in calls[0]
    assert "reasoning" not in calls[1]


def test_model_supports_temperature_detection() -> None:
    """The helper should detect reasoning models and allow regular ones."""

    assert not model_supports_temperature("o1-mini")
    assert not model_supports_temperature("o4-mini")
    assert model_supports_temperature(config.GPT41_MINI)


def test_model_supports_reasoning_detection() -> None:
    """The reasoning helper should match known reasoning model patterns."""

    assert model_supports_reasoning("o1-mini")
    assert model_supports_reasoning("o4-mini")
    assert not model_supports_reasoning(config.GPT41_MINI)


def test_extract_with_function(monkeypatch):
    """extract_with_function should parse JSON from a function call."""

    monkeypatch.setattr(
        openai_utils.api,
        "call_chat_api",
        lambda *a, **k: ChatCallResult(
            None,
            [
                {
                    "function": {
                        "input": {"job_title": "Dev"},
                    }
                }
            ],
            {},
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
    assert result.data["job_title"] == "Dev"


def test_extract_with_function_backfills_missing_sections(monkeypatch, caplog):
    """Heuristic fallbacks should supplement missing LLM sections."""

    job_text = """
Data Scientist (m/w/d)
Daten GmbH sucht Verstärkung!
Standort: Berlin
Deine Aufgaben:
- Entwickle Machine-Learning-Modelle
Benefits:
- Home Office
""".strip()

    payload = {
        "company": {},
        "position": {},
        "location": {},
        "responsibilities": {},
        "requirements": {},
        "employment": {},
        "compensation": {},
        "process": {},
        "meta": {},
    }

    call_result = ChatCallResult(
        None,
        [
            {
                "function": {
                    "input": payload,
                }
            }
        ],
        {},
    )

    monkeypatch.setattr(openai_utils.api, "call_chat_api", lambda *a, **k: call_result)

    with caplog.at_level(logging.INFO, logger="openai_utils.extraction"):
        result = extract_with_function(job_text, {})

    company_name = result.data["company"]["name"]
    title = result.data["position"]["job_title"]
    city = result.data["location"]["primary_city"]
    benefits = result.data["compensation"]["benefits"]
    responsibilities = result.data["responsibilities"]["items"]

    assert company_name == "Daten GmbH"
    assert title and "Data Scientist" in title
    assert city == "Berlin"
    assert benefits and "Home Office" in benefits[0]
    assert responsibilities and "Machine-Learning" in responsibilities[0]
    assert any(
        record.name == "openai_utils.extraction" and record.getMessage().startswith("Heuristics backfilled")
        for record in caplog.records
    )


def test_extract_with_function_falls_back_to_json_mode(monkeypatch):
    """If no function call is produced the helper should retry with JSON mode."""

    calls: list[dict[str, Any]] = []

    def _fake_call(messages: Sequence[dict[str, str]], **kwargs: Any) -> ChatCallResult:
        calls.append({"messages": messages, "kwargs": kwargs})
        if len(calls) == 1:
            return ChatCallResult("no structured output", [], {})
        return ChatCallResult('{"job_title": "Lead"}', [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", _fake_call)

    from core import schema as cs

    class _FakeProfile:
        def __init__(self, data: dict[str, Any]) -> None:
            self._data = data

        def model_dump(self) -> dict[str, Any]:
            return self._data

    monkeypatch.setattr(cs, "coerce_and_fill", lambda data: _FakeProfile(data))

    result = extract_with_function("text", {})
    assert len(calls) == 2
    assert "json_schema" in calls[1]["kwargs"]
    assert result.data["job_title"] == "Lead"


def test_extract_with_function_json_fallback_uses_context_payload(monkeypatch):
    """JSON mode retry should reuse the enriched context payload."""

    captured: list[dict[str, Any]] = []

    def _fake_call(messages: Sequence[dict[str, str]], **kwargs: Any) -> ChatCallResult:
        captured.append({"messages": messages, "kwargs": kwargs})
        if len(captured) == 1:
            return ChatCallResult("no structured output", [], {})
        return ChatCallResult('{"job_title": "Lead"}', [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", _fake_call)

    from core import schema as cs

    class _FakeProfile:
        def __init__(self, data: dict[str, Any]) -> None:
            self._data = data

        def model_dump(self) -> dict[str, Any]:
            return self._data

    monkeypatch.setattr(cs, "coerce_and_fill", lambda data: _FakeProfile(data))

    field_ctx = FieldExtractionContext(
        field="job_title",
        instruction="Prefer explicit titles",
        chunks=[RetrievedChunk(text="Job Title: Lead Engineer", score=0.88)],
    )
    global_ctx = [RetrievedChunk(text="Company overview", score=0.73)]

    extract_with_function(
        "ignored",
        {},
        field_contexts={"job_title": field_ctx},
        global_context=global_ctx,
    )

    assert len(captured) == 2
    retry_messages = captured[1]["messages"]
    assert retry_messages[0]["content"].endswith("Return only valid JSON that conforms exactly to the provided schema.")

    payload = json.loads(retry_messages[1]["content"])
    assert payload["global_context"][0]["text"] == "Company overview"
    assert payload["fields"][0]["field"] == "job_title"
    assert payload["fields"][0]["context"][0]["text"].startswith("Job Title")


def test_extract_with_function_json_fallback_reuses_payload(monkeypatch):
    """Retry call should reuse the original context payload without changes."""

    captured: list[dict[str, Any]] = []

    def _fake_call(messages: Sequence[dict[str, str]], **kwargs: Any) -> ChatCallResult:
        captured.append({"messages": messages, "kwargs": kwargs})
        if len(captured) == 1:
            return ChatCallResult("no structured output", [], {})
        return ChatCallResult('{"job_title": "Lead"}', [], {})

    monkeypatch.setattr(openai_utils.api, "call_chat_api", _fake_call)

    from core import schema as cs

    class _FakeProfile:
        def __init__(self, data: dict[str, Any]) -> None:
            self._data = data

        def model_dump(self) -> dict[str, Any]:
            return self._data

    monkeypatch.setattr(cs, "coerce_and_fill", lambda data: _FakeProfile(data))

    field_ctx = FieldExtractionContext(
        field="job_title",
        instruction="Prefer explicit titles",
        chunks=[RetrievedChunk(text="Job Title: Lead Engineer", score=0.88)],
    )
    global_ctx = [RetrievedChunk(text="Company overview", score=0.73)]

    extract_with_function(
        "ignored",
        {},
        field_contexts={"job_title": field_ctx},
        global_context=global_ctx,
    )

    assert len(captured) == 2
    initial_messages = captured[0]["messages"]
    retry_messages = captured[1]["messages"]

    assert retry_messages[1]["content"] == initial_messages[1]["content"]
    payload = json.loads(retry_messages[1]["content"])
    assert payload["global_context"][0]["text"] == "Company overview"
    assert payload["fields"][0]["context"][0]["text"].startswith("Job Title")


def test_extract_with_function_best_effort_fallback(monkeypatch):
    """When both primary strategies fail, a best-effort retry should run."""

    calls: list[dict[str, Any]] = []

    responses = [
        ChatCallResult(None, [], {}),
        ChatCallResult("   ", [], {}),
        ChatCallResult('{"job_title": "Fallback"}', [], {}),
    ]

    def _fake_call(messages: Sequence[dict[str, str]], **kwargs: Any) -> ChatCallResult:
        calls.append({"messages": messages, "kwargs": kwargs})
        return responses[len(calls) - 1]

    monkeypatch.setattr(openai_utils.api, "call_chat_api", _fake_call)

    from core import schema as cs

    class _FakeProfile:
        def __init__(self, data: dict[str, Any]) -> None:
            self._data = data

        def model_dump(self) -> dict[str, Any]:
            return self._data

    monkeypatch.setattr(cs, "coerce_and_fill", lambda data: _FakeProfile(data))

    result = extract_with_function("Some job text", {})

    assert result.data["job_title"] == "Fallback"
    assert len(calls) == 3
    assert "Return ONLY a JSON object" in calls[2]["messages"][0]["content"]


def test_extract_with_function_parses_json_payload(monkeypatch):
    """Structured extraction should accept strictly formatted JSON payloads."""

    monkeypatch.setattr(
        openai_utils.api,
        "call_chat_api",
        lambda *a, **k: ChatCallResult(
            None,
            [
                {
                    "function": {
                        "arguments": '{"job_title": "QA"}',
                        "input": '{"job_title": "QA"}',
                    }
                }
            ],
            {},
        ),
    )

    from core import schema as cs

    class _FakeProfile:
        def __init__(self, data: dict[str, Any]) -> None:
            self._data = data

        def model_dump(self) -> dict[str, Any]:
            return self._data

    monkeypatch.setattr(cs, "coerce_and_fill", lambda data: _FakeProfile(data))

    result = extract_with_function("text", {})
    assert result.data["job_title"] == "QA"


def test_extract_with_function_handles_malformed_json(monkeypatch):
    """Malformed JSON payloads should fall back to an empty profile in the UI."""

    st.session_state.clear()
    calls: list[dict[str, Any]] = []

    responses = [
        ChatCallResult(
            None,
            [
                {
                    "function": {
                        "input": "{",
                    }
                }
            ],
            {},
        ),
        ChatCallResult("{", [], {}),
    ]

    def _fake_call(messages, **kwargs):  # noqa: ANN001 - API signature is dynamic
        calls.append({"messages": messages, "kwargs": kwargs})
        return responses[len(calls) - 1]

    monkeypatch.setattr(openai_utils.api, "call_chat_api", _fake_call)

    result = extract_with_function("ignored", {})

    assert result.data == NeedAnalysisProfile().model_dump()
    assert len(calls) == 2
    assert st.session_state.get(StateKeys.EXTRACTION_MISSING) == []


def test_extract_with_function_handles_validation_error(monkeypatch):
    """Schema validation errors should trigger a partial extraction fallback."""

    st.session_state.clear()
    payload = {
        "requirements": {
            "hard_skills_required": "python",
        }
    }

    def _fake_call(messages, **kwargs):  # noqa: ANN001 - API signature is dynamic
        return ChatCallResult(
            None,
            [
                {
                    "function": {
                        "input": payload,
                    }
                }
            ],
            {},
        )

    monkeypatch.setattr(openai_utils.api, "call_chat_api", _fake_call)

    result = extract_with_function("ignored", {})

    assert result.data == NeedAnalysisProfile().model_dump()
    assert st.session_state.get(StateKeys.EXTRACTION_MISSING) == []


def test_extract_with_function_cli_mode_still_raises(monkeypatch):
    """When Streamlit is unavailable the helper should raise on invalid JSON."""

    calls: list[dict[str, Any]] = []

    responses = [
        ChatCallResult(
            None,
            [
                {
                    "function": {
                        "input": "{",
                    }
                }
            ],
            {},
        ),
        ChatCallResult("{", [], {}),
    ]

    def _fake_call(messages, **kwargs):  # noqa: ANN001 - API signature is dynamic
        calls.append({"messages": messages, "kwargs": kwargs})
        return responses[len(calls) - 1]

    monkeypatch.setattr(openai_utils.api, "call_chat_api", _fake_call)
    monkeypatch.setattr("openai_utils.extraction.st", None, raising=False)

    with pytest.raises(ValueError) as excinfo:
        extract_with_function("ignored", {})

    assert str(excinfo.value) == "Model returned invalid JSON"
    assert isinstance(excinfo.value.__cause__, Exception)
    assert len(calls) == 2


def test_call_chat_api_executes_tool(monkeypatch):
    """call_chat_api should execute mapped tools and return final content."""

    class _FirstResponse:
        def __init__(self) -> None:
            self.output = [
                {
                    "type": "response.tool_call",
                    "id": "1",
                    "call_id": "call_fn",
                    "function": {
                        "name": "get_skill_definition",
                        "input": {"skill": "Python"},
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
            tool_message = kwargs["input"][-1]
            assert tool_message["role"] == "tool"
            assert tool_message["tool_call_id"] == "call_fn"
            return _SecondResponse()

    class _FakeClient:
        responses = _FakeResponses()

    monkeypatch.setattr("openai_utils.api.client", _FakeClient(), raising=False)
    res = call_chat_api([{"role": "user", "content": "hi"}])
    assert res.content == "done"
    assert res.tool_calls[0]["function"]["name"] == "get_skill_definition"


def test_call_chat_api_executes_helper_tool(monkeypatch):
    """Tools created via build_function_tools should integrate with call_chat_api."""

    def _echo_tool(text: str) -> dict[str, str]:
        return {"echo": text.upper()}

    tool_specs = {
        "echo_tool": {
            "description": "Echo input in uppercase.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        }
    }
    tools, functions = build_function_tools(tool_specs, callables={"echo_tool": _echo_tool})

    class _FirstResponse:
        def __init__(self) -> None:
            self.output = [
                {
                    "type": "response.tool_call",
                    "id": "tool-1",
                    "call_id": "call_echo",
                    "function": {"name": "echo_tool", "input": {"text": "hello"}},
                }
            ]
            self.output_text = ""
            self.usage: dict[str, int] = {}

    class _SecondResponse:
        def __init__(self) -> None:
            self.output = []
            self.output_text = "done"
            self.usage: dict[str, int] = {}

    class _FakeResponses:
        def __init__(self) -> None:
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                function_names = {
                    tool.get("function", {}).get("name")
                    for tool in kwargs.get("tools", [])
                    if tool.get("type") == "function"
                }
                assert "echo_tool" in function_names
                return _FirstResponse()

            tool_message = kwargs["input"][-1]
            assert tool_message["role"] == "tool"
            assert tool_message["tool_call_id"] == "call_echo"
            assert json.loads(tool_message["content"])["echo"] == "HELLO"
            return _SecondResponse()

    class _FakeClient:
        responses = _FakeResponses()

    monkeypatch.setattr("openai_utils.api.client", _FakeClient(), raising=False)
    res = call_chat_api(
        [{"role": "user", "content": "hi"}],
        tools=tools,
        tool_functions=functions,
    )

    assert res.content == "done"
    assert res.tool_calls[0]["function"]["name"] == "echo_tool"


def test_get_client_uses_configured_timeout(monkeypatch):
    """The configured timeout should be passed to the OpenAI client."""

    captured: dict[str, Any] = {}

    class _DummyClient:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)
            self.responses = SimpleNamespace()

    monkeypatch.setattr(openai_utils.api, "client", None, raising=False)
    monkeypatch.setattr(openai_utils.api, "OPENAI_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(openai_utils.api, "OPENAI_BASE_URL", "https://api.example.com", raising=False)
    monkeypatch.setattr(openai_utils.api, "OPENAI_REQUEST_TIMEOUT", 321.0, raising=False)
    monkeypatch.setattr(openai_utils.api, "OpenAI", _DummyClient)

    openai_utils.api.get_client()

    assert captured["timeout"] == 321.0


def test_get_client_forwards_optional_org_and_project(monkeypatch):
    """Organisation and project overrides should be forwarded to the SDK."""

    captured: dict[str, Any] = {}

    class _DummyClient:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)
            self.responses = SimpleNamespace()

    monkeypatch.setattr(openai_utils.api, "client", None, raising=False)
    monkeypatch.setattr(openai_utils.api, "OPENAI_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(openai_utils.api, "OPENAI_BASE_URL", "", raising=False)
    monkeypatch.setattr(openai_utils.api, "OPENAI_REQUEST_TIMEOUT", 120.0, raising=False)
    monkeypatch.setattr(openai_utils.api, "OPENAI_ORGANIZATION", "org_123", raising=False)
    monkeypatch.setattr(openai_utils.api, "OPENAI_PROJECT", "proj_456", raising=False)
    monkeypatch.setattr(openai_utils.api, "OpenAI", _DummyClient)

    openai_utils.api.get_client()

    assert captured["organization"] == "org_123"
    assert captured["project"] == "proj_456"


def test_get_client_skips_blank_optional_identifiers(monkeypatch):
    """Blank organisation/project identifiers should not be forwarded."""

    captured: dict[str, Any] = {}

    class _DummyClient:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)
            self.responses = SimpleNamespace()

    monkeypatch.setattr(openai_utils.api, "client", None, raising=False)
    monkeypatch.setattr(openai_utils.api, "OPENAI_API_KEY", "test-key", raising=False)
    monkeypatch.setattr(openai_utils.api, "OPENAI_BASE_URL", "", raising=False)
    monkeypatch.setattr(openai_utils.api, "OPENAI_REQUEST_TIMEOUT", 120.0, raising=False)
    monkeypatch.setattr(openai_utils.api, "OPENAI_ORGANIZATION", "", raising=False)
    monkeypatch.setattr(openai_utils.api, "OPENAI_PROJECT", "   ", raising=False)
    monkeypatch.setattr(openai_utils.api, "OpenAI", _DummyClient)

    openai_utils.api.get_client()

    assert "organization" not in captured
    assert "project" not in captured


def test_execute_response_uses_configured_timeout(monkeypatch):
    """Responses.create should include the configured timeout argument."""

    captured: dict[str, Any] = {}

    class _DummyResponses:
        def create(self, **kwargs: Any) -> Any:
            captured.update(kwargs)
            return SimpleNamespace(output=[], usage={}, output_text="", id="resp")

    dummy_client = SimpleNamespace(responses=_DummyResponses())
    monkeypatch.setattr(openai_utils.api, "client", dummy_client, raising=False)
    monkeypatch.setattr(openai_utils.api, "OPENAI_REQUEST_TIMEOUT", 42.0, raising=False)

    response = openai_utils.api._execute_response({"input": []}, config.REASONING_MODEL)

    assert captured["timeout"] == 42.0
    assert response.id == "resp"


def test_chat_stream_uses_configured_timeout(monkeypatch):
    """Streaming responses should honour the configured timeout."""

    captured: dict[str, Any] = {}

    class _DummyStream:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: D401,B027
            return False

        def __iter__(self):
            return iter([])

        def get_final_response(self):
            return SimpleNamespace(output=[], usage={}, output_text="done", id="resp")

    class _DummyResponses:
        def stream(self, **kwargs: Any):
            captured.update(kwargs)
            return _DummyStream()

    dummy_client = SimpleNamespace(responses=_DummyResponses())

    monkeypatch.setattr(openai_utils.api, "client", dummy_client, raising=False)
    monkeypatch.setattr(openai_utils.api, "OPENAI_REQUEST_TIMEOUT", 77.0, raising=False)

    stream = openai_utils.api.ChatStream({"input": []}, config.REASONING_MODEL, task=None)
    assert list(stream) == []
    assert stream.result.content == "done"
    assert captured["timeout"] == 77.0


def test_chat_stream_missing_completion_event(monkeypatch, caplog):
    """Streaming should recover the final response when completion events are missing."""

    caplog.set_level("WARNING")

    class _DummyStream:
        def __init__(self) -> None:
            self._events = iter(
                [
                    {"type": "response.output_text.delta", "delta": "Hello"},
                ]
            )

        def __enter__(self):  # noqa: D401
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: D401,B027
            return False

        def __iter__(self):
            return self

        def __next__(self):
            return next(self._events)

        def get_final_response(self):
            raise RuntimeError("RuntimeError: Didn't receive a response.completed event.")

    responses_calls = {"create": 0}

    class _DummyResponses:
        def stream(self, **kwargs: Any):  # noqa: D401
            return _DummyStream()

        def create(self, **kwargs: Any):  # noqa: D401
            responses_calls["create"] += 1
            return SimpleNamespace(output_text="Recovered", usage={"input_tokens": 1}, id="resp-1")

    dummy_client = SimpleNamespace(responses=_DummyResponses())

    monkeypatch.setattr(openai_utils.api, "client", dummy_client, raising=False)

    stream = openai_utils.api.ChatStream({"input": []}, config.REASONING_MODEL, task=None)

    chunks = list(stream)
    assert chunks == ["Hello"]
    assert stream.text == "Hello"
    assert stream.result.content == "Recovered"
    assert stream.result.usage == {"input_tokens": 1}
    assert responses_calls["create"] == 1

    assert any("missing completion event" in message for message in caplog.messages)


def test_chat_stream_empty_response_falls_back_to_chat(monkeypatch, caplog):
    """An empty Responses stream should retry via Chat Completions."""

    caplog.set_level("WARNING")

    class _DummyStream:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: D401,B027
            return False

        def __iter__(self):  # noqa: D401
            return iter(())

        def get_final_response(self):  # noqa: D401
            return SimpleNamespace(output_text="", usage={}, id="resp-empty")

    class _DummyResponses:
        def stream(self, **kwargs: Any):  # noqa: D401
            return _DummyStream()

    class _DummyCompletions:
        @staticmethod
        def create(**kwargs: Any):  # noqa: D401
            return {
                "choices": [{"message": {"content": "Recovered via chat"}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 3},
                "id": "chat-fallback",
            }

    class _DummyChat:
        completions = _DummyCompletions()

    dummy_client = SimpleNamespace(responses=_DummyResponses(), chat=_DummyChat())

    monkeypatch.setattr(openai_utils.api, "client", dummy_client, raising=False)

    stream = openai_utils.api.ChatStream({"input": []}, config.REASONING_MODEL, task=None)

    chunks = list(stream)
    assert chunks == []
    assert stream.result.content == "Recovered via chat"
    assert stream.result.usage == {"input_tokens": 2, "output_tokens": 3}
    assert any("empty content" in message for message in caplog.messages)


def test_chat_stream_strict_json_schema_disables_stream(monkeypatch):
    """Strict JSON schema payloads should bypass streaming to avoid completion failures."""

    calls = {"stream": 0, "create": 0}

    class _DummyStream:
        def __iter__(self):  # pragma: no cover - should not be called
            calls["stream"] += 1
            yield "should-not-stream"

    class _DummyResponses:
        def stream(self, **kwargs: Any):  # pragma: no cover - should not be used
            calls["stream"] += 1
            return _DummyStream()

        def create(self, **kwargs: Any):
            calls["create"] += 1
            return SimpleNamespace(output_text="Recovered", usage={"input_tokens": 1}, id="resp-1")

    dummy_client = SimpleNamespace(responses=_DummyResponses())

    monkeypatch.setattr(openai_utils.api, "client", dummy_client, raising=False)

    strict_payload = {
        "input": [],
        "text": {
            "format": {
                "type": "json_schema",
                "json_schema": {"name": "foo", "schema": {}, "strict": True},
                "strict": True,
            }
        },
    }

    stream = openai_utils.api.ChatStream(strict_payload, config.REASONING_MODEL, task=None)

    assert list(stream) == []
    assert stream.text == ""
    assert stream.result.content == "Recovered"
    assert stream.result.usage == {"input_tokens": 1}
    assert calls == {"stream": 0, "create": 1}


def test_chat_stream_missing_final_payload_triggers_retry(monkeypatch):
    """Streaming should retry when no final payload is returned."""

    class _DummyStream:
        def __init__(self) -> None:
            self._events = iter(
                [
                    {"type": "response.output_text.delta", "delta": "Hallo"},
                ]
            )

        def __enter__(self):  # noqa: D401
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: D401,B027
            return False

        def __iter__(self):
            return self

        def __next__(self):
            return next(self._events)

        def get_final_response(self):
            return None

    responses_calls = {"create": 0}

    class _DummyResponses:
        def stream(self, **kwargs: Any):  # noqa: D401
            return _DummyStream()

        def create(self, **kwargs: Any):  # noqa: D401
            responses_calls["create"] += 1
            return SimpleNamespace(output_text="Recovered", usage={"input_tokens": 1}, id="resp-1")

    dummy_client = SimpleNamespace(responses=_DummyResponses())

    monkeypatch.setattr(openai_utils.api, "client", dummy_client, raising=False)

    stream = openai_utils.api.ChatStream({"input": []}, config.REASONING_MODEL, task=None)

    chunks = list(stream)
    assert chunks == ["Hallo"]
    assert stream.result.content == "Recovered"
    assert responses_calls["create"] == 1


def test_chat_stream_missing_completion_event_chat_fallback(monkeypatch):
    """Streaming should fall back to the Chat Completions API when Responses retry fails."""

    class _DummyStream:
        def __init__(self) -> None:
            self._events = iter(
                [
                    {"type": "response.output_text.delta", "delta": "Hi"},
                ]
            )

        def __enter__(self):  # noqa: D401
            return self

        def __exit__(self, exc_type, exc, tb):  # noqa: D401,B027
            return False

        def __iter__(self):
            return self

        def __next__(self):
            return next(self._events)

        def get_final_response(self):
            raise RuntimeError("RuntimeError: Didn't receive a response.completed event.")

    class _DummyResponses:
        def stream(self, **kwargs: Any):  # noqa: D401
            return _DummyStream()

        def create(self, **kwargs: Any):  # noqa: D401
            raise APIError("boom", response=_dummy_response(500), body="")

    class _DummyChatCompletions:
        def __init__(self) -> None:
            self.calls = 0

        def create(self, **kwargs: Any):
            self.calls += 1
            return SimpleNamespace(
                choices=[{"message": {"content": "Chat recovered"}}],
                usage={"prompt_tokens": 1, "completion_tokens": 2},
                id="chat-1",
            )

    chat_completions = _DummyChatCompletions()
    dummy_client = SimpleNamespace(
        responses=_DummyResponses(),
        chat=SimpleNamespace(completions=chat_completions),
    )

    monkeypatch.setattr(openai_utils.api, "client", dummy_client, raising=False)

    stream = openai_utils.api.ChatStream({"input": []}, config.REASONING_MODEL, task=None)

    chunks = list(stream)
    assert chunks == ["Hi"]
    assert chat_completions.calls == 1
    assert stream.result.content == "Chat recovered"
    assert stream.result.usage == {"input_tokens": 1, "output_tokens": 2}


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

    monkeypatch.setattr("openai_utils.api.client", _Client(), raising=False)
    with pytest.raises(RuntimeError, match="API key invalid"):
        call_chat_api([{"role": "user", "content": "hi"}])


def test_call_chat_api_rate_limit(monkeypatch):
    """Rate limit errors should surface a clear message."""

    class _Resp:
        def create(self, **kwargs):
            raise RateLimitError("quota", response=_dummy_response(429), body="")

    class _Client:
        responses = _Resp()

    monkeypatch.setattr("openai_utils.api.client", _Client(), raising=False)
    with pytest.raises(RuntimeError, match="rate limit"):
        call_chat_api([{"role": "user", "content": "hi"}])


def _make_streaming_error_event(message: str) -> dict[str, Any]:
    """Return a streaming event representing an error."""

    return {
        "type": "response.error",
        "error": {"message": message, "code": "rate_limit_exceeded"},
    }


def test_chat_stream_routes_streaming_errors(monkeypatch):
    """Streaming errors should surface in the UI before bubbling up."""

    recorded: list[str] = []

    def _capture_error(msg: str) -> None:
        recorded.append(msg)

    monkeypatch.setattr(st, "error", _capture_error)
    st.session_state["lang"] = "en"

    class _FakeStream:
        def __init__(self) -> None:
            self._events = iter([_make_streaming_error_event("Rate limit hit")])

        def __iter__(self):
            return self

        def __next__(self):
            return next(self._events)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get_final_response(self):  # pragma: no cover - not reached during error
            raise AssertionError("get_final_response should not be called on failure")

    class _FakeResponses:
        def stream(self, **_: Any):
            return _FakeStream()

    class _FakeClient:
        responses = _FakeResponses()

    monkeypatch.setattr(openai_utils.api, "client", _FakeClient(), raising=False)

    stream = openai_utils.api.ChatStream({}, "gpt-test", task=None)

    with pytest.raises(RuntimeError) as exc_info:
        list(stream)

    expected_message = resolve_message(openai_utils.api._RATE_LIMIT_ERROR_MESSAGE, lang="en")
    assert recorded == [expected_message]
    assert str(exc_info.value) == expected_message
