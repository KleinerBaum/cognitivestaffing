"""Tests for hardened OpenAI Responses payload generation (v2025)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Mapping

import pytest

from llm import openai_responses


class _FakeResponsesClient:
    """Simple stub capturing the last payload passed to responses.create."""

    def __init__(self) -> None:
        self.captured: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> Any:  # pragma: no cover - simple stub
        self.captured = dict(kwargs)
        return SimpleNamespace(
            output=[],
            output_text="{}",
            usage={},
            id="resp-test",
        )


class _FakeClient:
    def __init__(self, responses_client: _FakeResponsesClient) -> None:
        self.responses = responses_client


@pytest.fixture(autouse=True)
def _patch_client(monkeypatch: pytest.MonkeyPatch) -> _FakeResponsesClient:
    """Provide a fake OpenAI client for each test."""

    fake_responses = _FakeResponsesClient()
    monkeypatch.setattr(openai_responses, "get_client", lambda: _FakeClient(fake_responses))
    return fake_responses


def test_v2025_minimal_payload(_patch_client: _FakeResponsesClient) -> None:
    """Payloads must stick to the minimal v2025 schema contract."""

    fmt = openai_responses.build_json_schema_format(
        name="need_analysis_profile",
        schema={"type": "object"},
    )
    result = openai_responses.call_responses(
        messages=[{"role": "user", "content": "hi"}],
        model="gpt-4o-mini",
        response_format=fmt,
    )

    assert result.response_id == "resp-test"

    captured = _patch_client.captured
    assert captured is not None, "Expected responses.create to be invoked"
    assert set(captured) == {"model", "input", "timeout", "text"}
    assert captured["model"] == "gpt-4o-mini"
    assert isinstance(captured["input"], list)
    assert captured["timeout"] == openai_responses.OPENAI_REQUEST_TIMEOUT

    text_section = captured["text"]
    assert set(text_section) == {"format"}
    format_payload = text_section["format"]
    assert format_payload["type"] == "json_schema"
    assert format_payload["name"] == "need_analysis_profile"
    assert format_payload["schema"] == {"type": "object"}


def test_schema_guard_triggers_fallback(monkeypatch: pytest.MonkeyPatch, _patch_client: _FakeResponsesClient) -> None:
    """Missing schemas must be caught before dispatch (RESPONSES_PAYLOAD_GUARD)."""

    fmt: Mapping[str, Any] = {"name": "broken", "schema": None}

    dispatched = False

    def _fail_create(**_: Any) -> None:  # pragma: no cover - guard ensures no call
        nonlocal dispatched
        dispatched = True

    monkeypatch.setattr(_patch_client, "create", _fail_create)

    result = openai_responses.call_responses_safe(
        messages=[{"role": "user", "content": "hi"}],
        model="gpt-4o-mini",
        response_format=fmt,
    )

    assert result is None
    assert dispatched is False


def test_temperature_omitted_when_unsupported(
    monkeypatch: pytest.MonkeyPatch, _patch_client: _FakeResponsesClient
) -> None:
    """Temperature should be absent when the model rejects it (TEMP_SUPPORTED)."""

    monkeypatch.setattr(openai_responses, "model_supports_temperature", lambda model: False)

    fmt = openai_responses.build_json_schema_format(
        name="need_analysis_profile",
        schema={"type": "object"},
    )

    openai_responses.call_responses(
        messages=[{"role": "user", "content": "hi"}],
        model="o1-mini",
        response_format=fmt,
        temperature=0.7,
    )

    captured = _patch_client.captured
    assert captured is not None
    assert "temperature" not in captured
