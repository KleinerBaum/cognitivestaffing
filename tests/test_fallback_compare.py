import json
from types import SimpleNamespace

import pytest
from openai import OpenAIError

import openai_utils.api as api
from config import APIMode, ModelTask, resolve_api_mode, set_api_mode
from models.need_analysis import NeedAnalysisProfile


class _ChatStub:
    def __init__(self, content: str):
        self._content = content
        self.completions = SimpleNamespace(create=self._create)

    def _create(self, **_: object) -> SimpleNamespace:
        return SimpleNamespace(
            choices=[{"message": {"content": self._content}}],
            usage={"prompt_tokens": 1, "completion_tokens": 1},
            id="chat-stub",
        )


class _ClientStub:
    def __init__(self, content: str):
        self.chat = _ChatStub(content)
        self.responses = SimpleNamespace(create=lambda **_: None)


def _profile_payload() -> dict:
    return NeedAnalysisProfile().model_dump()


def _messages() -> list[dict[str, str]]:
    return [{"role": "user", "content": "test"}]


def test_responses_fallback_to_chat_produces_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    expected_profile = _profile_payload()
    stub_client = _ClientStub(json.dumps(expected_profile))

    def _raise_bad_request(*_: object, **__: object) -> None:
        raise OpenAIError("bad request")

    monkeypatch.setattr(api, "get_client", lambda: stub_client)
    monkeypatch.setattr(api, "_execute_response", _raise_bad_request)
    previous_mode = resolve_api_mode()
    set_api_mode(APIMode.RESPONSES)
    try:
        result = api.call_chat_api(
            _messages(),
            model="fallback-model",
            json_schema=api.build_need_analysis_json_schema_payload(),
            task=ModelTask.EXTRACTION,
        )
    finally:
        set_api_mode(previous_mode)

    parsed = json.loads(result.content or "{}")
    assert parsed == expected_profile


def test_classic_chat_alignment(monkeypatch: pytest.MonkeyPatch) -> None:
    expected_profile = _profile_payload()
    chat_response = SimpleNamespace(
        choices=[{"message": {"content": json.dumps(expected_profile)}}],
        usage={"prompt_tokens": 1, "completion_tokens": 1},
        id="chat-primary",
    )

    monkeypatch.setattr(api, "_execute_response", lambda *_, **__: chat_response)
    previous_mode = resolve_api_mode()
    set_api_mode(APIMode.CLASSIC)
    try:
        result = api.call_chat_api(
            _messages(),
            model="classic-model",
            json_schema=api.build_need_analysis_json_schema_payload(),
            task=ModelTask.EXTRACTION,
        )
    finally:
        set_api_mode(previous_mode)

    parsed = json.loads(result.content or "{}")
    assert parsed == expected_profile
