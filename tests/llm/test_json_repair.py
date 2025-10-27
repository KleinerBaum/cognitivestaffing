"""Tests for the JSON repair helper."""

from __future__ import annotations

import json

import pytest

from llm import json_repair
from llm.json_repair import repair_profile_payload


class DummyResponse:
    """Minimal Responses API stub."""

    def __init__(self, content: str):
        self.content = content
        self.usage: dict[str, int] = {}
        self.response_id = "resp"
        self.raw_response: dict[str, str] = {}


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

    monkeypatch.setattr(json_repair, "call_responses", fake_call)

    errors = [{"loc": ("company", "logo_url"), "msg": "invalid url"}]
    result = repair_profile_payload({"company": {"logo_url": "invalid"}}, errors=errors)

    assert result == {"company": {"logo_url": "https://example.com/logo.svg"}}
    assert isinstance(captured["messages"], list)
    assert "company.logo_url" in captured["messages"][1]["content"]
