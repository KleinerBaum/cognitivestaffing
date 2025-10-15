import json
from copy import deepcopy
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

import pytest

import httpx
import openai_utils
from config import ModelTask
from openai_utils import (
    ChatCallResult,
    call_chat_api,
    stream_chat_api,
    extract_with_function,
    model_supports_reasoning,
    model_supports_temperature,
)
from openai import AuthenticationError, RateLimitError
import streamlit as st

from constants.keys import StateKeys
from llm.rag_pipeline import FieldExtractionContext, RetrievedChunk


@pytest.fixture(autouse=True)
def reset_temperature_cache(monkeypatch):
    """Ensure temperature capability cache is cleared between tests."""

    monkeypatch.setattr(openai_utils.api, "_MODELS_WITHOUT_TEMPERATURE", set(), raising=False)
    yield


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
            calls.append(deepcopy(kwargs.get("input", [])))
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

    def _fake_prepare(messages: Sequence[dict[str, Any]], **_: Any):
        return ({"model": "test", "input": list(messages)}, "test", [], {})

    def _fake_execute(_: Mapping[str, Any], __: str | None):
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
        max_tokens: int | None = None,
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
                "max_tokens": max_tokens,
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

    assert captured["text"]["format"]["type"] == "json_schema"
    assert captured["text"]["format"]["name"] == schema["name"]
    assert captured["text"]["format"]["schema"] == schema["schema"]
    assert captured["text"]["format"]["strict"] is True


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
        model="gpt-5-mini",
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
    """Function tools should expose nested metadata while built-ins stay bare."""

    captured: dict[str, Any] = {}

    class _FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            for tool in kwargs.get("tools", []):
                if tool.get("type") == "function":
                    fn_block = tool.get("function", {})
                    assert "name" in fn_block and fn_block["name"]
                    assert "parameters" in fn_block
                    assert "name" not in tool
                else:
                    assert "function" not in tool
                    assert "name" not in tool
            return type("R", (), {"output": [], "output_text": "", "usage": {}})()

    class _FakeClient:
        responses = _FakeResponses()

    monkeypatch.setattr("openai_utils.api.client", _FakeClient(), raising=False)
    call_chat_api(
        [],
        tools=[{"type": "function", "function": {"name": "fn", "parameters": {}}}],
    )

    assert any(tool.get("type") == "web_search" for tool in captured.get("tools", []))


def test_prepare_payload_includes_web_search_tools():
    """The payload should always advertise OpenAI web search tools."""

    payload, _, _, _ = openai_utils.api._prepare_payload(
        messages=[{"role": "user", "content": "hi"}],
        model="gpt-5-mini",
        temperature=None,
        max_tokens=None,
        json_schema=None,
        tools=[{"type": "function", "function": {"name": "custom", "parameters": {}}}],
        tool_choice=None,
        tool_functions={},
        reasoning_effort=None,
        verbosity=None,
        extra=None,
        include_analysis_tools=True,
    )

    tool_types = {tool.get("type") for tool in payload["tools"]}
    assert "web_search" in tool_types
    assert "web_search_preview" in tool_types

    for tool in payload["tools"]:
        if tool.get("type") == "function":
            fn_payload = tool.get("function", {})
            assert fn_payload.get("name")
        else:
            assert "name" not in tool


def test_prepare_payload_normalises_legacy_tool_choice():
    """Legacy function tool choices should be translated to the nested schema."""

    payload, _, _, _ = openai_utils.api._prepare_payload(
        messages=[{"role": "user", "content": "hi"}],
        model="gpt-5-mini",
        temperature=None,
        max_tokens=None,
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
        verbosity=None,
        extra=None,
        include_analysis_tools=False,
    )

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
    tool = openai_utils.build_extraction_tool("cognitive_needs_extract", schema)
    spec = tool[0]
    assert spec["type"] == "function"
    fn_payload = spec["function"]
    assert fn_payload["name"] == "cognitive_needs_extract"
    assert fn_payload["parameters"]["type"] == "object"
    assert fn_payload["strict"] is True


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
    params = tool[0]["function"]["parameters"]
    assert params["required"] == ["outer"]
    outer = params["properties"]["outer"]
    assert outer["required"] == ["inner"]
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
    st.session_state["reasoning_effort"] = "minimal"

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
        model="gpt-5-nano",
        reasoning_effort="high",
    )
    assert "reasoning" not in captured


def test_call_chat_api_includes_explicit_verbosity(monkeypatch):
    """Explicit verbosity settings should be forwarded to the API payload."""

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
    assert captured["verbosity"] == "high"


def test_call_chat_api_uses_session_verbosity_default(monkeypatch):
    """When omitted the helper should fall back to the session verbosity."""

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
    assert captured["verbosity"] == "low"


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

    calls: list[dict[str, Any]] = []

    class _FakeBadRequestError(Exception):
        def __init__(self, message: str) -> None:
            super().__init__(message)
            self.message = message

    class _FakeResponses:
        def create(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                raise _FakeBadRequestError("Unsupported parameter: 'temperature' is not supported with this model.")
            return type("R", (), {"output": [], "output_text": "", "usage": {}})()

    class _FakeClient:
        responses = _FakeResponses()

    monkeypatch.setattr("openai_utils.api.client", _FakeClient(), raising=False)
    monkeypatch.setattr("openai_utils.api.BadRequestError", _FakeBadRequestError)

    result = call_chat_api(
        [{"role": "user", "content": "hi"}],
        model="gpt-5-mini",
        temperature=0.5,
    )

    assert len(calls) == 2
    assert "temperature" in calls[0]
    assert "temperature" not in calls[1]
    assert result.tool_calls == []
    assert not model_supports_temperature("gpt-5-mini")


def test_model_supports_temperature_detection() -> None:
    """The helper should detect reasoning models and allow regular ones."""

    assert not model_supports_temperature("o1-mini")
    assert not model_supports_temperature("gpt-5-reasoning")
    assert model_supports_temperature("gpt-5-mini")


def test_model_supports_reasoning_detection() -> None:
    """The reasoning helper should match known reasoning model patterns."""

    assert model_supports_reasoning("o1-mini")
    assert model_supports_reasoning("gpt-5-reasoning")
    assert not model_supports_reasoning("gpt-5-nano")


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
            assert kwargs["input"][1]["role"] == "tool"
            assert kwargs["input"][1]["tool_call_id"] == "call_fn"
            return _SecondResponse()

    class _FakeClient:
        responses = _FakeResponses()

    monkeypatch.setattr("openai_utils.api.client", _FakeClient(), raising=False)
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
