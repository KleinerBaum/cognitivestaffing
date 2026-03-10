import json
from types import SimpleNamespace

import pytest
import config.models as model_config
from openai import BadRequestError
from requests import Response
from llm import client
from llm.openai_responses import UnrecoverableSchemaShortCircuitError
from models.need_analysis import NeedAnalysisProfile


class _FakeParser:
    format_instructions = ""

    def parse(self, content: str):
        return NeedAnalysisProfile(), json.loads(content)


class _FakeChatResult:
    def __init__(self, content: str):
        self.content = content
        self.usage: dict[str, int] = {}
        self.response_id = "chat"
        self.raw_response = None


def test_responses_schema_error_switches_to_chat_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, int] = {"chat": 0, "responses": 0}

    def _raise_invalid_schema(*_: object, **__: object):
        calls["responses"] += 1
        return None

    def _fake_chat_api(*_: object, **__: object) -> _FakeChatResult:
        calls["chat"] += 1
        return _FakeChatResult(json.dumps({"title": "Engineer"}))

    monkeypatch.setattr(client, "call_responses_safe", _raise_invalid_schema)
    monkeypatch.setattr(client, "call_chat_api", _fake_chat_api)
    monkeypatch.setattr(client, "get_need_analysis_output_parser", lambda: _FakeParser())
    monkeypatch.setattr(client, "_responses_api_enabled", lambda: True)
    monkeypatch.setattr(client, "_strict_extraction_enabled", lambda: True)

    outcome = client._structured_extraction(
        {
            "messages": [{"role": "user", "content": "text"}],
            "model": model_config.GPT4O_MINI,
            "reasoning_effort": None,
            "verbosity": None,
            "retries": 0,
            "source_text": "",
        }
    )

    assert calls["responses"] == 2
    assert calls["chat"] == 1
    assert isinstance(json.loads(outcome.content), dict)
    assert outcome.low_confidence is True


def test_unrecoverable_schema_400_short_circuits_after_single_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, int] = {"chat": 0, "responses": 0}

    def _raise_invalid_schema(*_: object, **__: object):
        calls["responses"] += 1
        raise UnrecoverableSchemaShortCircuitError("invalid schema")

    def _fake_chat_api(*_: object, **kwargs: object) -> _FakeChatResult:
        calls["chat"] += 1
        assert kwargs.get("use_response_format") is False
        assert "json_schema" not in kwargs
        return _FakeChatResult(json.dumps({"title": "Engineer"}))

    monkeypatch.setattr(client, "call_responses_safe", _raise_invalid_schema)
    monkeypatch.setattr(client, "call_chat_api", _fake_chat_api)
    monkeypatch.setattr(client, "get_need_analysis_output_parser", lambda: _FakeParser())
    monkeypatch.setattr(client, "_responses_api_enabled", lambda: True)
    monkeypatch.setattr(client, "_strict_extraction_enabled", lambda: True)

    outcome = client._structured_extraction(
        {
            "messages": [{"role": "user", "content": "text"}],
            "model": model_config.GPT4O_MINI,
            "reasoning_effort": None,
            "verbosity": None,
            "retries": 2,
            "source_text": "",
        }
    )

    assert calls["responses"] == 1
    assert calls["chat"] == 1
    assert outcome.schema_unrecoverable_short_circuit is True


def test_bad_request_response_format_schema_short_circuits_without_model_rotation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, int] = {"chat": 0, "responses": 0, "alternate_model": 0}
    fake_response = Response()
    fake_response.status_code = 400
    fake_response.headers = {}
    fake_response.request = SimpleNamespace()

    def _raise_invalid_schema(*_: object, **__: object):
        calls["responses"] += 1
        raise BadRequestError(
            "Invalid schema for response_format 'need_analysis_profile'",
            response=fake_response,
            body={"error": {"param": "response_format"}},
        )

    def _fake_chat_api(*_: object, **kwargs: object) -> _FakeChatResult:
        calls["chat"] += 1
        assert kwargs.get("use_response_format") is False
        assert "json_schema" not in kwargs
        return _FakeChatResult(json.dumps({"title": "Engineer"}))

    def _fail_if_rotating(*_: object, **__: object) -> str:
        calls["alternate_model"] += 1
        return "unexpected"

    monkeypatch.setattr(client, "call_responses_safe", _raise_invalid_schema)
    monkeypatch.setattr(client, "call_chat_api", _fake_chat_api)
    monkeypatch.setattr(client, "get_model_for", _fail_if_rotating)
    monkeypatch.setattr(client, "get_need_analysis_output_parser", lambda: _FakeParser())
    monkeypatch.setattr(client, "_responses_api_enabled", lambda: True)
    monkeypatch.setattr(client, "_strict_extraction_enabled", lambda: True)

    outcome = client._structured_extraction(
        {
            "messages": [{"role": "user", "content": "text"}],
            "model": model_config.GPT4O_MINI,
            "reasoning_effort": None,
            "verbosity": None,
            "retries": 2,
            "source_text": "",
        }
    )

    assert calls["responses"] == 1
    assert calls["chat"] == 1
    assert calls["alternate_model"] == 0
    assert outcome.schema_unrecoverable_short_circuit is True
