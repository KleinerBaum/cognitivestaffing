"""Tests for the JSON repair helper."""

from __future__ import annotations

import json

import pytest
from pydantic import HttpUrl, TypeAdapter

from llm import json_repair
from llm.json_repair import repair_profile_payload
from models.need_analysis import NeedAnalysisProfile


class DummyResponse:
    """Minimal Responses API stub."""

    def __init__(self, content: str):
        self.content = content
        self.usage: dict[str, int] = {}
        self.response_id = "resp"
        self.raw_response: dict[str, str] = {}
        self.used_chat_fallback = False


def test_repair_profile_payload_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(json_repair, "is_llm_enabled", lambda: False)
    json_repair._load_schema.cache_clear()

    result = repair_profile_payload({"company": {}}, errors=[])

    assert result is None


def test_repair_profile_payload_invokes_responses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(json_repair, "is_llm_enabled", lambda: True)
    json_repair._load_schema.cache_clear()

    schema = {"type": "object", "properties": {}, "additionalProperties": True}
    monkeypatch.setattr(json_repair, "_load_schema", lambda: schema)

    captured: dict[str, object] = {}

    def fake_call(messages, **kwargs):  # type: ignore[unused-ignore]
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        payload = {"company": {"logo_url": "https://example.com/logo.svg"}}
        return DummyResponse(json.dumps(payload))

    monkeypatch.setattr(json_repair, "call_responses_safe", fake_call)

    errors = [{"loc": ("company", "logo_url"), "msg": "invalid url"}]
    result = repair_profile_payload({"company": {"logo_url": "invalid"}}, errors=errors)

    assert result == {"company": {"logo_url": "https://example.com/logo.svg"}}
    assert isinstance(captured["messages"], list)
    assert "company.logo_url" in captured["messages"][1]["content"]


def test_repair_profile_payload_normalizes_interview_stages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(json_repair, "is_llm_enabled", lambda: True)
    json_repair._load_schema.cache_clear()

    schema = {"type": "object", "properties": {}, "additionalProperties": True}
    monkeypatch.setattr(json_repair, "_load_schema", lambda: schema)

    payload = NeedAnalysisProfile().model_dump()
    payload["process"]["interview_stages"] = []

    def fake_call(messages, **kwargs):  # type: ignore[unused-ignore]
        return DummyResponse(json.dumps(payload))

    monkeypatch.setattr(json_repair, "call_responses_safe", fake_call)

    result = repair_profile_payload({"process": {"interview_stages": []}}, errors=None)

    assert result["process"]["interview_stages"] is None


def test_repair_profile_payload_serializes_http_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(json_repair, "is_llm_enabled", lambda: True)
    json_repair._load_schema.cache_clear()

    schema = {"type": "object", "properties": {}, "additionalProperties": True}
    monkeypatch.setattr(json_repair, "_load_schema", lambda: schema)

    logo_url = TypeAdapter(HttpUrl).validate_python("https://example.com/logo.svg")
    captured: dict[str, str] = {}

    def fake_call(messages, **kwargs):  # type: ignore[unused-ignore]
        captured["content"] = messages[1]["content"]
        payload = {"company": {"logo_url": "https://example.com/logo.svg"}}
        return DummyResponse(json.dumps(payload))

    monkeypatch.setattr(json_repair, "call_responses_safe", fake_call)

    errors = [{"loc": ("company", "logo_url"), "msg": "invalid url"}]
    result = repair_profile_payload({"company": {"logo_url": logo_url}}, errors=errors)

    assert result == {"company": {"logo_url": "https://example.com/logo.svg"}}
    assert "https://example.com/logo.svg" in captured.get("content", "")
