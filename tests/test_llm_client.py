"""Tests for the OpenAI LLM client helper."""

import json
from types import SimpleNamespace

import pytest
import streamlit as st

from openai_utils import ChatCallResult

import llm.client as client
from models.need_analysis import NeedAnalysisProfile
from llm.openai_responses import ResponsesCallResult


def fake_responses_call(*args, **kwargs):  # noqa: D401
    """Return a fake Responses API result."""

    kwargs.pop("logger_instance", None)
    kwargs.pop("context", None)
    kwargs.pop("allow_empty", None)
    return ResponsesCallResult(
        content=NeedAnalysisProfile().model_dump_json(),
        usage={},
        response_id="resp_123",
        raw_response={},
    )


def test_extract_json_smoke(monkeypatch):
    """Smoke test for the extraction helper."""

    monkeypatch.setattr(client, "call_responses_safe", fake_responses_call)
    monkeypatch.setattr(
        client,
        "call_chat_api",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("fallback not expected")),
    )
    out = client.extract_json("text")
    assert isinstance(out, str) and out != ""


def test_extract_json_validation_failure_triggers_fallback(monkeypatch):
    """Invalid structured output should fall back to plain text."""

    calls = {"structured": 0, "fallback": 0}

    def _fake_responses(messages, *, response_format=None, **kwargs):
        calls["structured"] += 1
        return ResponsesCallResult(
            content=json.dumps({"company": "acme"}),
            usage={},
            response_id="resp_1",
            raw_response={},
        )

    def _fake_chat(messages, *, json_schema=None, **kwargs):
        if json_schema is not None:
            calls["structured"] += 1
            return ChatCallResult(
                content=json.dumps({"company": "acme"}),
                tool_calls=[],
                usage={},
            )
        calls["fallback"] += 1
        return ChatCallResult(content=json.dumps({"fallback": True}), tool_calls=[], usage={})

    monkeypatch.setattr(client, "call_responses_safe", _fake_responses)
    monkeypatch.setattr(client, "call_chat_api", _fake_chat)
    out = client.extract_json("text")
    payload = json.loads(out)
    assert payload == {"fallback": True}
    assert calls == {"structured": 1, "fallback": 1}


def test_extract_json_minimal_prompt(monkeypatch):
    """Minimal mode should use the simplified prompt template."""

    captured: dict[str, list[dict[str, str]]] = {}

    def _fake(messages, *, response_format=None, **kwargs):
        captured["messages"] = list(messages)
        return ResponsesCallResult(
            content=NeedAnalysisProfile().model_dump_json(),
            usage={},
            response_id="resp_min",
            raw_response={},
        )

    monkeypatch.setattr(client, "call_responses_safe", _fake)
    monkeypatch.setattr(
        client,
        "call_chat_api",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("fallback not expected")),
    )
    out = client.extract_json("text", minimal=True)
    assert "Return JSON only" in captured["messages"][0]["content"]
    assert json.loads(out)["company"]


def test_extract_json_forwards_context(monkeypatch):
    """Providing hints should be forwarded into the prompt builder."""

    st.session_state.clear()
    captured: dict[str, str | list[dict[str, str]]] = {}

    def _fake_build(
        text: str,
        *,
        title: str | None = None,
        company: str | None = None,
        url: str | None = None,
        locked_fields: dict[str, str] | None = None,
    ) -> list[dict[str, str]]:
        captured["text"] = text
        captured["title"] = title or ""
        captured["company"] = company or ""
        captured["url"] = url or ""
        captured["locked_fields"] = locked_fields or {}
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "user"},
        ]
        captured["messages"] = messages
        return messages

    monkeypatch.setattr(client, "build_extract_messages", _fake_build)
    monkeypatch.setattr(
        client,
        "_STRUCTURED_EXTRACTION_CHAIN",
        SimpleNamespace(
            invoke=lambda payload: NeedAnalysisProfile().model_dump_json(),
        ),
    )
    monkeypatch.setattr(
        client,
        "call_chat_api",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("fallback not expected")),
    )

    out = client.extract_json(
        "Job text",
        title="Locked Engineer",
        company="Locked Corp",
        url="https://example.com/job",
        locked_fields={
            "position.job_title": "Locked Engineer",
            "company.name": "Locked Corp",
        },
    )

    assert json.loads(out)
    assert captured["text"] == "Job text"
    assert captured["title"] == "Locked Engineer"
    assert captured["company"] == "Locked Corp"
    assert captured["url"] == "https://example.com/job"
    assert captured["locked_fields"] == {
        "position.job_title": "Locked Engineer",
        "company.name": "Locked Corp",
    }
    assert captured["messages"][0]["content"] == "sys"


def test_extract_json_logs_warning_on_responses_failure(monkeypatch, caplog):
    """A Responses outage should log a warning and fall back to chat completions."""

    caplog.set_level("WARNING")

    def _boom(*args, **kwargs):
        raise RuntimeError("Responses failure")

    monkeypatch.setattr("llm.openai_responses.call_responses", _boom)

    fallback_payload = {"fallback": True}

    def _fake_chat(messages, *, json_schema=None, **kwargs):
        return ChatCallResult(
            content=json.dumps(fallback_payload),
            tool_calls=[],
            usage={},
        )

    monkeypatch.setattr(client, "call_chat_api", _fake_chat)

    out = client.extract_json("Example text")
    assert json.loads(out) == fallback_payload
    assert any(
        "structured extraction" in record.getMessage() for record in caplog.records if record.levelname == "WARNING"
    )


def test_extract_json_reapplies_locked_fields(monkeypatch):
    """Locked field hints should be merged back into the final payload."""

    locked_values = {
        "company.contact_email": "m.m@rheinbahn.de",
        "location.primary_city": "Flexible Arbeitszeiten",
    }

    def _fake(messages, *, json_schema=None, **kwargs):
        assert json_schema is not None
        profile = NeedAnalysisProfile()
        profile.company.contact_email = "override@example.com"
        profile.location.primary_city = "Düsseldorf"
        return ChatCallResult(content=profile.model_dump_json(), tool_calls=[], usage={})

    monkeypatch.setattr(client, "call_chat_api", _fake)
    out = client.extract_json("text", locked_fields=locked_values)
    payload = json.loads(out)
    assert payload["company"]["contact_email"] == "m.m@rheinbahn.de"
    assert payload["location"]["primary_city"] == "Flexible Arbeitszeiten"


def test_assert_closed_schema_raises() -> None:
    """The helper should detect foreign key references."""

    with pytest.raises(ValueError):
        client._assert_closed_schema({"$ref": "#/foo"})


def test_generate_error_report_missing_required() -> None:
    """Missing required fields should be reported clearly."""

    report = client._generate_error_report({"process": {"stakeholders": [{}]}})
    assert "'role' is a required property" in report
