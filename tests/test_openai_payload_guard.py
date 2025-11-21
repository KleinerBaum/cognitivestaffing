"""Unit tests for OpenAI payload sanitation and error logging helpers."""

from types import SimpleNamespace
from typing import Any

import openai_utils.api as openai_api


def test_execute_response_prunes_responses_fields_when_forcing_chat(monkeypatch):
    """Responses-style payloads should be cleaned before chat invocations."""

    captured: dict[str, Any] = {}

    class _DummyCompletions:
        def create(self, **kwargs: Any) -> Any:  # noqa: D401
            captured.update(kwargs)
            return SimpleNamespace(output=[], usage={}, output_text="done", id="resp")

    dummy_client = SimpleNamespace(chat=SimpleNamespace(completions=_DummyCompletions()))

    monkeypatch.setattr(openai_api, "client", dummy_client, raising=False)

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
    assert "previous_response_id" not in captured
    assert captured["metadata"] == {"source": "test"}


def test_execute_response_prunes_chat_fields_in_responses_mode(monkeypatch):
    """Chat-only fields should be stripped before hitting the Responses API."""

    captured: dict[str, Any] = {}

    class _DummyResponses:
        def create(self, **kwargs: Any) -> Any:  # noqa: D401
            captured.update(kwargs)
            return SimpleNamespace(output=[], usage={}, output_text="", id="resp")

    dummy_client = SimpleNamespace(responses=_DummyResponses())

    monkeypatch.setattr(openai_api, "client", dummy_client, raising=False)

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
