"""Tests for the OpenAI LLM client helper."""

import pytest

from openai_utils import ChatCallResult

import llm.client as client


def fake_call_chat_api(*args, **kwargs):  # noqa: D401
    """Return a fake OpenAI chat call result."""

    return ChatCallResult(content="{}", tool_calls=[], usage={})


def test_extract_json_smoke(monkeypatch):
    """Smoke test for the extraction helper."""

    monkeypatch.setattr(client, "call_chat_api", fake_call_chat_api)
    out = client.extract_json("text")
    assert isinstance(out, str) and out != ""


def test_assert_closed_schema_raises() -> None:
    """The helper should detect foreign key references."""

    with pytest.raises(ValueError):
        client._assert_closed_schema({"$ref": "#/foo"})


def test_generate_error_report_missing_required() -> None:
    """Missing required fields should be reported clearly."""

    report = client._generate_error_report({"position": {"job_title": "x"}})
    assert "'company' is a required property" in report
