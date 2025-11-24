from types import SimpleNamespace

import config
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
    monkeypatch.setattr(config, "USE_RESPONSES_API", True, raising=False)
    monkeypatch.setattr(config, "USE_CLASSIC_API", False, raising=False)

    result = openai_api.call_chat_api(
        messages=[{"role": "user", "content": "hi"}],
        json_schema={"name": "test", "schema": {"type": "object"}},
        task=config.ModelTask.EXTRACTION,
    )

    assert result.content == "fallback"
    assert "responses" in captured
    assert "chat" in captured
