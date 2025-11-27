"""Unit tests for OpenAI payload sanitation and error logging helpers."""

from copy import deepcopy
from types import SimpleNamespace
from typing import Any

from openai import OpenAIError

import config
import config.models as model_config
import openai_utils.api as openai_api
import openai_utils.payloads as payloads


def test_execute_response_prunes_responses_fields_when_forcing_chat(monkeypatch):
    """Responses-style payloads should be cleaned before chat invocations."""

    captured: dict[str, Any] = {}

    class _DummyCompletions:
        def create(self, **kwargs: Any) -> Any:  # noqa: D401
            captured.update(kwargs)
            return SimpleNamespace(output=[], usage={}, output_text="done", id="resp")

    dummy_client = SimpleNamespace(chat=SimpleNamespace(completions=_DummyCompletions()))

    monkeypatch.setattr(openai_api, "client", dummy_client, raising=False)
    monkeypatch.setattr(openai_api.openai_client, "get_client", lambda: dummy_client)

    payload = {
        "model": "gpt-test",
        "input": [{"role": "user", "content": "hi"}],
        "text": {"format": {"type": "json_schema"}},
        "max_output_tokens": 77,
        "previous_response_id": "resp_A",
        "metadata": {"source": "test"},
    }

    openai_api._execute_response(payload, "gpt-test", api_mode="chat")

    assert captured["messages"] == payload["input"]
    assert "input" not in captured
    assert "text" not in captured
    assert "max_output_tokens" not in captured
    assert captured.get("max_completion_tokens") == 77
    assert "previous_response_id" not in captured
    assert captured["metadata"] == {"source": "test"}


def test_execute_response_prunes_chat_fields_in_responses_mode(monkeypatch):
    """Chat-only fields should be stripped before hitting the Responses API."""

    captured: dict[str, Any] = {}

    class _DummyResponses:
        def create(self, **kwargs: Any) -> Any:  # noqa: D401
            captured.update(kwargs)
            return SimpleNamespace(output=[], usage={}, output_text="", id="resp")

    dummy_client = SimpleNamespace(
        responses=_DummyResponses(), chat=SimpleNamespace(completions=_DummyResponses())
    )

    monkeypatch.setattr(openai_api, "client", dummy_client, raising=False)
    monkeypatch.setattr(openai_api.openai_client, "get_client", lambda: dummy_client)

    payload = {
        "model": "gpt-test",
        "messages": [{"role": "user", "content": "Hallo"}],
        "functions": [{"name": "do"}],
        "function_call": "auto",
        "response_format": {"type": "json_schema"},
        "max_completion_tokens": 11,
        "metadata": {"source": "responses"},
    }

    openai_api._execute_response(payload, "gpt-test", api_mode="responses")

    assert captured["input"] == payload["messages"]
    assert "messages" not in captured
    assert "functions" not in captured
    assert "function_call" not in captured
    assert "response_format" not in captured
    assert "max_completion_tokens" not in captured
    assert captured["metadata"] == {"source": "responses"}


def test_chat_fallback_payload_strips_strict(monkeypatch, caplog):
    """Responses fallbacks should drop strict flags before Chat Completions calls."""

    caplog.set_level("DEBUG")

    config.set_api_mode(config.APIMode.RESPONSES)

    captured: dict[str, Any] = {}

    def _boom(*_: Any, **__: Any) -> None:
        raise OpenAIError("fail")

    class _DummyCompletions:
        def create(self, **kwargs: Any) -> Any:  # noqa: D401
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[{"message": {"content": "ok"}}],
                usage={},
                id="chat-fallback",
            )

    dummy_client = SimpleNamespace(chat=SimpleNamespace(completions=_DummyCompletions()))

    monkeypatch.setattr(openai_api, "_execute_response", _boom)
    monkeypatch.setattr(openai_api, "get_client", lambda: dummy_client)
    monkeypatch.setattr(payloads, "requires_chat_completions", lambda *_: False)

    schema_bundle = openai_api.build_schema_format_bundle(
        {"name": "fallback_schema", "schema": {"type": "object"}, "strict": True}
    )

    result = openai_api.call_chat_api(
        [{"role": "user", "content": "hi"}],
        model=model_config.GPT4O_MINI,
        json_schema={
            "name": schema_bundle.name,
            "schema": deepcopy(schema_bundle.schema),
            "strict": True,
        },
        api_mode=config.APIMode.RESPONSES,
    )

    response_format = captured.get("response_format", {})
    assert response_format.get("type") == "json_schema"
    assert "strict" not in response_format
    assert response_format.get("json_schema", {}).get("strict") is True
    assert result.content == "ok"
