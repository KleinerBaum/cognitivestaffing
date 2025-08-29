"""Tests for the OpenAI LLM client helper."""

import pytest

import llm.client as client


class _FakeResponse:
    """Minimal stand-in for an OpenAI Responses API result."""

    def __init__(self, text: str = "{}") -> None:
        self.output_text = text
        self.usage: dict[str, int] = {}


def fake_create(**kwargs):  # noqa: D401
    """Return a fake OpenAI response object."""

    return _FakeResponse(text="{}")


def test_extract_json_smoke(monkeypatch):
    """Smoke test for the extraction helper."""

    monkeypatch.setattr(client.OPENAI_CLIENT.responses, "create", fake_create)
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
