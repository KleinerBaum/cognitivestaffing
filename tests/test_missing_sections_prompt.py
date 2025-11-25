"""Tests for the missing-sections extraction prompt wiring."""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest

import llm.client as client
from llm.openai_responses import ResponsesCallResult


def test_missing_sections_prompt_invocation(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    """Ensure the dedicated missing-sections prompt is used when retrying extraction."""

    caplog.set_level(logging.INFO, logger="cognitive_needs.llm")

    calls: dict[str, Any] = {}

    def fake_get(key: str, **_: Any) -> str:
        calls["system_key"] = key
        return "SYSTEM_PROMPT"

    def fake_format(key: str, **params: Any) -> str:
        calls.setdefault("user_calls", []).append((key, params))
        return f"USER_PROMPT {params['sections']}"

    def fake_responses_call(
        messages: list[dict[str, str]],
        **_: Any,
    ) -> ResponsesCallResult:
        calls["messages"] = messages
        return ResponsesCallResult(
            content=json.dumps({"responsibilities": {"items": ["Design APIs"]}}),
            usage={},
            response_id="resp-missing",
            raw_response={},
            used_chat_fallback=False,
        )

    monkeypatch.setattr(client.prompt_registry, "get", fake_get)
    monkeypatch.setattr(client.prompt_registry, "format", fake_format)
    monkeypatch.setattr(client, "call_responses_safe", fake_responses_call)

    result = client._retry_missing_sections(
        "We need an engineer to design APIs.",
        ["responsibilities.items"],
        model="gpt-4o-mini",
        retries=1,
    )

    assert result is not None
    assert result.get("responsibilities", {}).get("items") == ["Design APIs"]
    assert calls["system_key"] == "llm.extraction.missing_sections.system"
    assert calls["user_calls"][0][0] == "llm.extraction.missing_sections.user"
    assert "responsibilities.items" in calls["user_calls"][0][1]["sections"]
    assert any("missing sections" in record.getMessage() for record in caplog.records)
    assert calls["messages"][0]["content"] == "SYSTEM_PROMPT"
    assert "responsibilities.items" in calls["messages"][1]["content"]
