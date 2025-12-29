from __future__ import annotations

import types

import pytest

import config.models as model_config
from openai_utils.client import OpenAIClient


def test_create_response_routes_responses_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """OpenAIClient should call the Responses endpoint when requested."""

    calls: list[tuple[str, dict]] = []

    def _record_call(name: str):
        def _wrapper(**kwargs):
            calls.append((name, kwargs))
            return {"ok": True}

        return _wrapper

    fake_responses = types.SimpleNamespace(create=_record_call("responses"))
    fake_chat_completions = types.SimpleNamespace(create=_record_call("chat"))
    fake_client = types.SimpleNamespace(
        responses=fake_responses, chat=types.SimpleNamespace(completions=fake_chat_completions)
    )

    client = OpenAIClient()
    monkeypatch.setattr(client, "get_client", lambda: fake_client)

    responses_payload = {
        "model": model_config.GPT52_MINI,
        "messages": [{"role": "user", "content": "hi"}],
        "_api_mode": "responses",
    }
    client._create_response_with_timeout(dict(responses_payload), api_mode="responses")

    chat_payload = {
        "model": model_config.GPT41_MINI,
        "messages": [{"role": "user", "content": "hello"}],
        "_api_mode": "chat",
    }
    client._create_response_with_timeout(dict(chat_payload), api_mode="chat")

    assert calls[0][0] == "responses"
    assert calls[0][1]["input"] == responses_payload["messages"]
    assert calls[1][0] == "chat"
    assert calls[1][1]["messages"] == chat_payload["messages"]
