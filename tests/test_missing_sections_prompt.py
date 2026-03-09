"""Tests for the missing-sections extraction prompt wiring."""

from __future__ import annotations

import json
import logging
from typing import Any

import pytest

import config.models as model_config
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
        return f"USER_PROMPT {params.get('sections') or params.get('fields')}"

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
        model=model_config.GPT4O_MINI,
        retries=1,
    )

    assert result is not None
    assert result.get("responsibilities", {}).get("items") == ["Design APIs"]
    assert calls["system_key"] == "llm.extraction.missing_sections.system"
    keys = [entry[0] for entry in calls["user_calls"]]
    assert "llm.extraction.missing_sections.user" in keys
    assert "llm.extraction.targeted_lists.user" in keys
    missing_call = next(entry for entry in calls["user_calls"] if entry[0] == "llm.extraction.missing_sections.user")
    assert "responsibilities.items" in missing_call[1]["sections"]
    assert any("missing sections" in record.getMessage() for record in caplog.records)
    assert calls["messages"][0]["content"] == "SYSTEM_PROMPT"
    assert "responsibilities.items" in calls["messages"][1]["content"]


def test_missing_sections_uses_targeted_second_pass_for_list_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """Targeted list fields should trigger the dedicated second extraction pass."""

    calls: dict[str, Any] = {"get": [], "format": []}

    def fake_get(key: str, **_: Any) -> str:
        calls["get"].append(key)
        return f"PROMPT::{key}"

    def fake_format(key: str, **params: Any) -> str:
        calls["format"].append((key, params))
        return f"PROMPT::{key}::{params.get('fields') or params.get('sections')}"

    def fake_responses_call(messages: list[dict[str, str]], **_: Any) -> ResponsesCallResult:
        content_blob = "\n".join(message.get("content", "") for message in messages)
        if "targeted_lists" in content_blob:
            return ResponsesCallResult(
                content=json.dumps(
                    {
                        "requirements": {
                            "hard_skills_required": ["Python", "SQL"],
                            "soft_skills_required": ["Communication"],
                        },
                        "responsibilities": {"items": ["Design APIs"]},
                    }
                ),
                usage={},
                response_id="resp-targeted",
                raw_response={},
                used_chat_fallback=False,
            )
        return ResponsesCallResult(
            content=json.dumps({}),
            usage={},
            response_id="resp-generic",
            raw_response={},
            used_chat_fallback=False,
        )

    monkeypatch.setattr(client.prompt_registry, "get", fake_get)
    monkeypatch.setattr(client.prompt_registry, "format", fake_format)
    monkeypatch.setattr(client, "call_responses_safe", fake_responses_call)

    result = client._retry_missing_sections(
        "You will design APIs. Erfahrung in Python und SQL. Teamfähigkeit ist wichtig.",
        [
            "responsibilities.items",
            "requirements.hard_skills_required",
            "requirements.soft_skills_required",
        ],
        model=model_config.GPT4O_MINI,
        retries=1,
    )

    assert result is not None
    requirements = result.get("requirements", {})
    assert requirements.get("hard_skills_required") == ["Python", "SQL"]
    assert requirements.get("soft_skills_required") == ["Communication"]
    assert result.get("responsibilities", {}).get("items") == ["Design APIs"]
    assert "llm.extraction.targeted_lists.system" in calls["get"]
    assert any(call[0] == "llm.extraction.targeted_lists.user" for call in calls["format"])
