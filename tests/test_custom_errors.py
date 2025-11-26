from typing import Any

import pytest

import openai_utils.api as api
from openai import BadRequestError, RateLimitError
from openai_utils.errors import ExternalServiceError, LLMResponseFormatError, SchemaValidationError


class _DummyBadRequest(BadRequestError):
    def __init__(self, message: str) -> None:  # noqa: D401 - test helper
        Exception.__init__(self, message)
        self.message = message


class _DummyRateLimit(RateLimitError):
    def __init__(self, message: str) -> None:  # noqa: D401 - test helper
        Exception.__init__(self, message)
        self.message = message


@pytest.fixture(autouse=True)
def _force_llm_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_llm_disabled", lambda: False)
    monkeypatch.setattr(api, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(api, "_build_chat_fallback_payload", lambda *_args, **_kwargs: None)


def _mock_payload_response() -> dict[str, Any]:
    return {"choices": [], "usage": {}, "id": "resp_123"}


def test_schema_validation_error_wrap(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_schema_error(_payload: Any, _model: str | None, api_mode: Any = None) -> Any:
        raise _DummyBadRequest("invalid_json_schema: missing required")

    monkeypatch.setattr(api, "_execute_response", _raise_schema_error)

    with pytest.raises(SchemaValidationError) as excinfo:
        api.call_chat_api(
            messages=[{"role": "user", "content": "hi"}],
            json_schema={"name": "TestSchema", "schema": {"type": "object", "properties": {}}},
        )

    assert excinfo.value.schema == "TestSchema"
    assert excinfo.value.model is not None


def test_response_format_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_execute_response", lambda *_args, **_kwargs: _mock_payload_response())
    monkeypatch.setattr(api, "_extract_output_text", lambda _response: "raw-text")
    monkeypatch.setattr(api, "_normalise_content_payload", lambda _content: None)

    with pytest.raises(LLMResponseFormatError) as excinfo:
        api.call_chat_api(
            messages=[{"role": "user", "content": "hi"}],
            json_schema={"name": "TestSchema", "schema": {"type": "object", "properties": {}}},
        )

    assert excinfo.value.schema == "TestSchema"
    assert excinfo.value.raw_content == "raw-text"


def test_external_service_error_wrap(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_rate_limit(_payload: Any, _model: str | None, api_mode: Any = None) -> Any:
        raise _DummyRateLimit("rate limit")

    monkeypatch.setattr(api, "_execute_response", _raise_rate_limit)

    with pytest.raises(ExternalServiceError) as excinfo:
        api.call_chat_api(messages=[{"role": "user", "content": "hi"}])

    assert excinfo.value.service == "openai"
    assert excinfo.value.model is not None
