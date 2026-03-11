from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

import config
from config.models import GPT51_NANO, ModelTask
from llm.openai_responses import build_json_schema_format, call_responses
from openai_utils.payloads import _build_chat_fallback_payload, _prepare_payload


def test_prepare_payload_uses_responses_text_format_for_structured_output() -> None:
    schema = {
        "name": "NeedProfile",
        "schema": {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]},
        "strict": True,
    }

    request = _prepare_payload(
        [{"role": "user", "content": "hi"}],
        model=GPT51_NANO,
        temperature=None,
        max_completion_tokens=128,
        json_schema=schema,
        tools=None,
        tool_choice=None,
        tool_functions=None,
        reasoning_effort="minimal",
        verbosity="low",
        extra=None,
        task=ModelTask.DEFAULT,
        previous_response_id="resp_prev",
        api_mode="responses",
        use_response_format=True,
    )

    payload = request.payload
    assert "text" in payload
    assert payload["text"]["format"]["type"] == "json_schema"
    assert "response_format" not in payload
    assert payload["previous_response_id"] == "resp_prev"


def test_prepare_payload_rejects_unsupported_nano_tool_types() -> None:
    with pytest.raises(ValueError, match="Unsupported tool type"):
        _prepare_payload(
            [{"role": "user", "content": "hi"}],
            model=GPT51_NANO,
            temperature=None,
            max_completion_tokens=None,
            json_schema=None,
            tools=[{"type": "computer_use"}],
            tool_choice=None,
            tool_functions=None,
            reasoning_effort=None,
            verbosity=None,
            extra=None,
            task=ModelTask.DEFAULT,
            previous_response_id=None,
            api_mode="responses",
            use_response_format=True,
        )


def test_strict_mode_blocks_cross_family_chat_fallback_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "STRICT_NANO_ONLY", True, raising=False)

    with pytest.raises(RuntimeError, match="Strict nano mode"):
        _build_chat_fallback_payload(
            {"model": "gpt-4o-mini", "input": [{"role": "user", "content": "hi"}]},
            [{"role": "user", "content": "hi"}],
            schema_bundle=None,
        )


def test_call_responses_forces_responses_mode_without_legacy_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _fake_call_chat_api(messages: list[dict[str, Any]], **kwargs: Any) -> Any:
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return SimpleNamespace(content="{}", usage={}, response_id="resp_1", raw_response={})

    monkeypatch.setattr("llm.openai_responses.call_chat_api", _fake_call_chat_api)

    result = call_responses(
        [{"role": "user", "content": "hi"}],
        model=GPT51_NANO,
        response_format=build_json_schema_format(name="Out", schema={"type": "object"}),
    )

    assert result.content == "{}"
    assert captured["kwargs"]["api_mode"] == config.APIMode.RESPONSES
    assert captured["kwargs"]["allow_legacy_fallback"] is False


def test_prepare_payload_preserves_supported_tools_in_strict_nano_mode() -> None:
    request = _prepare_payload(
        [{"role": "user", "content": "Find evidence for this role profile."}],
        model=GPT51_NANO,
        temperature=None,
        max_completion_tokens=200,
        json_schema={
            "name": "Out",
            "schema": {
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
                "additionalProperties": False,
            },
            "strict": True,
        },
        tools=[
            {"type": "web_search", "name": "web_search"},
            {"type": "file_search", "name": "file_search", "file_search": {"vector_store_ids": ["vs_123"]}},
        ],
        tool_choice=None,
        tool_functions=None,
        reasoning_effort="minimal",
        verbosity="low",
        extra=None,
        task=ModelTask.DEFAULT,
        previous_response_id="resp_tools",
        api_mode="responses",
        use_response_format=True,
    )

    payload = request.payload
    assert payload["model"] == GPT51_NANO
    assert payload["previous_response_id"] == "resp_tools"
    assert payload["tools"][0]["type"] == "web_search"
    assert payload["tools"][1]["type"] == "file_search"
    assert "response_format" not in payload
    assert payload["text"]["format"]["type"] == "json_schema"


def test_prepare_payload_forces_nano_model_in_strict_mode() -> None:
    request = _prepare_payload(
        [{"role": "user", "content": "hi"}],
        model="gpt-4o-mini",
        temperature=None,
        max_completion_tokens=None,
        json_schema=None,
        tools=[{"type": "function", "function": {"name": "fn", "parameters": {"type": "object"}}}],
        tool_choice=None,
        tool_functions={"fn": lambda: {"ok": True}},
        reasoning_effort=None,
        verbosity=None,
        extra=None,
        task=ModelTask.DEFAULT,
        previous_response_id=None,
        api_mode="responses",
        use_response_format=True,
    )

    assert request.payload["model"] == GPT51_NANO


def test_prepare_payload_quick_vs_precise_effort_and_output_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    from openai_utils import payloads as payload_module

    monkeypatch.setattr(payload_module, "get_reasoning_mode", lambda: "quick")
    monkeypatch.setattr(payload_module, "model_supports_reasoning", lambda _model: True)
    quick = _prepare_payload(
        [{"role": "user", "content": "hi"}],
        model=GPT51_NANO,
        temperature=None,
        max_completion_tokens=321,
        json_schema=None,
        tools=None,
        tool_choice=None,
        tool_functions=None,
        reasoning_effort="high",
        verbosity="low",
        extra=None,
        task=ModelTask.DEFAULT,
        previous_response_id=None,
        api_mode="responses",
        use_response_format=True,
    )

    assert quick.payload["reasoning"]["effort"] == "minimal"
    assert quick.payload["verbosity"] == "low"
    assert quick.payload["max_output_tokens"] == 321

    monkeypatch.setattr(payload_module, "get_reasoning_mode", lambda: "precise")
    precise = _prepare_payload(
        [{"role": "user", "content": "hi"}],
        model=GPT51_NANO,
        temperature=None,
        max_completion_tokens=222,
        json_schema=None,
        tools=None,
        tool_choice=None,
        tool_functions=None,
        reasoning_effort="minimal",
        verbosity="medium",
        extra=None,
        task=ModelTask.DEFAULT,
        previous_response_id=None,
        api_mode="responses",
        use_response_format=True,
    )

    assert precise.payload["reasoning"]["effort"] == "low"
    assert precise.payload["verbosity"] == "medium"
    assert precise.payload["max_output_tokens"] == 222
