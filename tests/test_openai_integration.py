from types import SimpleNamespace

import config
import config.models as model_config
import openai_utils.api as openai_api
import pytest
from openai import BadRequestError


def test_responses_bad_request_falls_back_to_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    """Responses 400 errors should fall back to Chat Completions automatically."""

    captured: dict[str, dict] = {}

    fake_response = SimpleNamespace(request=SimpleNamespace(), status_code=400, headers={})

    class _DummyResponses:
        def create(self, **kwargs):  # type: ignore[override]
            captured["responses"] = kwargs
            raise BadRequestError(
                "Unknown parameter: 'response_format.strict'",
                response=fake_response,
                body=None,
            )

    class _DummyCompletions:
        @staticmethod
        def create(**kwargs):  # type: ignore[override]
            captured["chat"] = kwargs
            return {
                "choices": [{"message": {"content": "fallback"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2},
                "id": "chat-id",
            }

    class _DummyChat:
        completions = _DummyCompletions()

    dummy_client = SimpleNamespace(responses=_DummyResponses(), chat=_DummyChat())

    monkeypatch.setattr(openai_api, "client", dummy_client, raising=False)
    monkeypatch.setattr(openai_api, "get_client", lambda: dummy_client)
    config.set_api_mode(True)

    result = openai_api.call_chat_api(
        messages=[{"role": "user", "content": "hi"}],
        json_schema={"name": "test", "schema": {"type": "object"}},
        task=model_config.ModelTask.EXTRACTION,
    )

    assert result.content == "fallback"
    assert "responses" in captured
    assert "chat" in captured


def test_schema_bad_request_degrades_then_falls_back_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Schema errors should retry same model without schema, then fallback to next model."""

    calls: list[dict[str, object]] = []

    fake_response = SimpleNamespace(request=SimpleNamespace(), status_code=400, headers={})

    def _fake_execute_response(payload, model, *, api_mode=None):  # type: ignore[override]
        calls.append(dict(payload))
        if len(calls) == 1:
            raise BadRequestError(
                "invalid_json_schema: unsupported schema for this model",
                response=fake_response,
                body={"error": {"code": "invalid_json_schema"}},
            )
        if len(calls) == 2:
            raise BadRequestError(
                "invalid_json_schema: still rejected",
                response=fake_response,
                body={"error": {"code": "invalid_json_schema"}},
            )
        return SimpleNamespace(output=[], output_text="ok", usage={})

    monkeypatch.setattr(openai_api, "_execute_response", _fake_execute_response)
    config.set_api_mode(True)

    result = openai_api.call_chat_api(
        messages=[{"role": "user", "content": "hi"}],
        model=model_config.GPT4O,
        json_schema={"name": "test", "schema": {"type": "object"}},
    )

    assert result.content == "ok"
    assert len(calls) == 3
    assert calls[0]["model"] == model_config.GPT4O
    assert "response_format" in calls[0]
    assert calls[1]["model"] == model_config.GPT4O
    assert "response_format" not in calls[1]
    assert calls[2]["model"] != model_config.GPT4O
