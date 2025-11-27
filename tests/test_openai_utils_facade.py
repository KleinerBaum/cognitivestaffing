from __future__ import annotations

from typing import Any, Mapping

import pytest
from openai import APITimeoutError

import streamlit as st
from config import APIMode, ModelTask
import config.models as model_config
from openai_utils.client import OpenAIClient
from openai_utils.payloads import _prepare_payload
from openai_utils.schemas import build_schema_format_bundle, sanitize_response_format_payload


def test_openai_client_retries_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    client = OpenAIClient()
    call_count = {"value": 0}

    def _fake_create(payload: Mapping[str, Any], *, api_mode: str) -> dict[str, str]:
        call_count["value"] += 1
        if call_count["value"] == 1:
            raise APITimeoutError("timeout")
        return {"status": "ok", "mode": api_mode}

    monkeypatch.setattr(client, "_create_response_with_timeout", _fake_create)

    result = client.execute_request(
        {"model": model_config.GPT4O, "messages": []},
        model_config.GPT4O,
        api_mode="chat",
    )

    assert result == {"status": "ok", "mode": "chat"}
    assert call_count["value"] == 2


def test_schema_bundle_sanitises_response_format() -> None:
    schema_payload = {
        "name": "example_payload",
        "schema": {
            "type": "object",
            "properties": {"field": {"type": "string"}},
        },
        "strict": True,
    }

    bundle = build_schema_format_bundle(schema_payload)

    assert bundle.name == "example_payload"
    assert bundle.responses_format["json_schema"]["schema"]["properties"]["field"]["type"] == "string"
    assert bundle.chat_response_format["type"] == "json_schema"

    cleaned = sanitize_response_format_payload(bundle.responses_format)
    assert cleaned["json_schema"]["schema"]["properties"] == {"field": {"type": "string"}}


def test_prepare_payload_builds_chat_and_responses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(st, "session_state", {})
    messages = [{"role": "user", "content": "hello"}]
    schema_payload = {"name": "demo", "schema": {"type": "object", "properties": {"field": {"type": "string"}}}}

    responses_request = _prepare_payload(
        messages,
        model=model_config.GPT4O,
        temperature=0.1,
        max_completion_tokens=128,
        json_schema=schema_payload,
        tools=None,
        tool_choice=None,
        tool_functions=None,
        reasoning_effort="high",
        extra={"metadata": {"trace": "1"}},
        include_analysis_tools=False,
        task=ModelTask.DEFAULT,
        previous_response_id=None,
        api_mode=APIMode.RESPONSES,
        use_response_format=True,
    )

    assert responses_request.payload["input"] == messages
    assert responses_request.payload["text"]["format"]["name"] == "demo"
    assert responses_request.api_mode_override == APIMode.RESPONSES.value

    chat_request = _prepare_payload(
        messages,
        model=model_config.GPT4O,
        temperature=0.3,
        max_completion_tokens=64,
        json_schema=schema_payload,
        tools=None,
        tool_choice=None,
        tool_functions=None,
        reasoning_effort="low",
        extra=None,
        include_analysis_tools=False,
        task=ModelTask.DEFAULT,
        previous_response_id=None,
        api_mode=APIMode.CLASSIC,
        use_response_format=True,
    )

    assert chat_request.payload["messages"] == messages
    assert "response_format" in chat_request.payload
    assert chat_request.api_mode_override == APIMode.CLASSIC.value

