"""Tests for the OpenAI LLM client helper."""

import json
from typing import Any
from types import SimpleNamespace

import pytest
import streamlit as st

import config
import config.models as model_config
from openai_utils import ChatCallResult

import llm.client as client
import llm.openai_responses as responses_module
from llm.output_parsers import NeedAnalysisParserError
from llm.prompts import PreExtractionInsights
from models.need_analysis import NeedAnalysisProfile
from llm.openai_responses import ResponsesCallResult
from utils.json_repair import JsonRepairResult, JsonRepairStatus


@pytest.fixture(autouse=True)
def force_responses_mode():
    previous_mode = config.USE_RESPONSES_API
    config.set_api_mode(True)
    try:
        yield
    finally:
        config.set_api_mode(previous_mode)


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


def test_run_pre_extraction_analysis_enforces_required_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pre-analysis schema should require every declared property."""

    captured: dict[str, Any] = {}

    def _fake_chat(*_args: Any, **kwargs: Any) -> ChatCallResult:
        captured["json_schema"] = kwargs.get("json_schema")
        return ChatCallResult(
            content=json.dumps(
                {
                    "relevant_fields": ["company.name"],
                    "missing_fields": ["process.overview"],
                    "summary": "Notes",
                }
            ),
            tool_calls=[],
            usage={},
        )

    monkeypatch.setattr(client, "build_preanalysis_messages", lambda *_a, **_k: [])
    monkeypatch.setattr(client, "select_model", lambda *_a, **_k: model_config.GPT4O_MINI)
    monkeypatch.setattr(client, "call_chat_api", _fake_chat)

    insights = client._run_pre_extraction_analysis("Sample text")

    assert insights is not None
    schema = captured["json_schema"]["schema"]
    assert set(schema["required"]) == set(schema["properties"].keys())


def test_extract_json_smoke(monkeypatch):
    """Smoke test for the extraction helper."""

    monkeypatch.setattr(client, "call_responses_safe", fake_responses_call)
    monkeypatch.setattr(responses_module, "call_responses_safe", fake_responses_call)
    monkeypatch.setattr(
        client,
        "_run_pre_extraction_analysis",
        lambda *a, **k: None,
    )
    chat_calls = {"count": 0}

    def _fake_chat(*args, **kwargs):
        chat_calls["count"] += 1
        return ChatCallResult(
            content=NeedAnalysisProfile().model_dump_json(),
            tool_calls=[],
            usage={},
        )

    monkeypatch.setattr(client, "call_chat_api", _fake_chat)
    out = client.extract_json("text")
    assert isinstance(out, str) and out != ""


def test_extract_json_validation_failure_triggers_structured_retry(monkeypatch):
    """Invalid Responses output should retry via chat with the schema."""

    calls = {"responses": 0, "chat": 0}

    def _fake_responses(messages, *, response_format=None, **kwargs):
        calls["responses"] += 1
        return ResponsesCallResult(
            content=json.dumps({"company": "acme"}),
            usage={},
            response_id="resp_1",
            raw_response={},
        )

    def _fake_chat(messages, *, json_schema=None, **kwargs):
        calls["chat"] += 1
        return ChatCallResult(
            content=NeedAnalysisProfile().model_dump_json(),
            tool_calls=[],
            usage={},
        )

    monkeypatch.setattr(client, "call_responses_safe", _fake_responses)
    monkeypatch.setattr(responses_module, "call_responses_safe", _fake_responses)
    monkeypatch.setattr(client, "call_chat_api", _fake_chat)
    monkeypatch.setattr(
        client,
        "_run_pre_extraction_analysis",
        lambda *a, **k: None,
    )
    out = client.extract_json("text")
    payload = json.loads(out)
    assert payload["company"]["name"] is None
    assert calls == {"responses": 1, "chat": 1}


def test_extract_json_plain_fallback_is_sanitized(monkeypatch):
    """When structured attempts fail, the plain fallback should be parsed."""

    calls = {"responses": 0, "chat_structured": 0, "chat_plain": 0}

    def _fake_responses(messages, *, response_format=None, **kwargs):
        calls["responses"] += 1
        return ResponsesCallResult(
            content=json.dumps({"company": "acme"}),
            usage={},
            response_id="resp_2",
            raw_response={},
        )

    def _fake_chat(messages, *, json_schema=None, **kwargs):
        if json_schema is not None:
            calls["chat_structured"] += 1
            raise RuntimeError("structured retry failed")
        calls["chat_plain"] += 1
        return ChatCallResult(
            content=json.dumps({"company": {"name": "Fallback GmbH"}}),
            tool_calls=[],
            usage={},
        )

    monkeypatch.setattr(client, "call_responses_safe", _fake_responses)
    monkeypatch.setattr(responses_module, "call_responses_safe", _fake_responses)
    monkeypatch.setattr(client, "call_chat_api", _fake_chat)
    monkeypatch.setattr(
        client,
        "_run_pre_extraction_analysis",
        lambda *a, **k: None,
    )
    out = client.extract_json("text")
    payload = json.loads(out)
    assert payload["company"]["name"] == "Fallback GmbH"
    assert calls["responses"] == 1
    assert calls["chat_plain"] == 1
    assert calls["chat_structured"] == 0


def test_structured_extraction_recovers_missing_sections(monkeypatch):
    """Missing sections should trigger a targeted retry before fallback."""

    missing_errors = [{"loc": ("responsibilities", "items"), "msg": "missing"}]

    class _FakeParser:
        def parse(self, content: str):  # noqa: D401
            raise NeedAnalysisParserError(
                "missing responsibilities",
                raw_text=content,
                data=NeedAnalysisProfile().model_dump(mode="python"),
                original=None,
                errors=missing_errors,
            )

    def _fake_responses(messages, *, response_format=None, **kwargs):
        return ResponsesCallResult(
            content=json.dumps({"responsibilities": {"items": ["Design APIs"]}}),
            usage={},
            response_id="resp_missing",
            raw_response={},
            used_chat_fallback=False,
        )

    monkeypatch.setattr(client, "call_responses_safe", _fake_responses)
    monkeypatch.setattr(responses_module, "call_responses_safe", _fake_responses)
    monkeypatch.setattr(client, "get_need_analysis_output_parser", lambda: _FakeParser())
    monkeypatch.setattr(client, "_summarise_prompt", lambda *_: "digest")

    payload = {
        "messages": [{"role": "user", "content": "text"}],
        "model": model_config.GPT4O_MINI,
        "reasoning_effort": "low",
        "verbosity": None,
        "retries": 1,
        "source_text": "We need an engineer to design APIs.",
    }

    output = client._structured_extraction(payload)
    parsed = json.loads(output)

    assert parsed["responsibilities"]["items"] == ["Design APIs"]


def test_extract_json_skips_responses_when_api_mode_disabled(monkeypatch) -> None:
    """Disabling Responses API should force the chat path immediately."""

    previous_mode = config.USE_RESPONSES_API
    config.set_api_mode(False)

    def _boom(*_args: object, **_kwargs: object) -> None:  # pragma: no cover - enforced by the test
        raise AssertionError("Responses API call should be bypassed when disabled")

    chat_calls = {"count": 0}

    def _fake_chat(messages, *, json_schema=None, **kwargs):
        chat_calls["count"] += 1
        assert json_schema is not None
        return ChatCallResult(
            content=NeedAnalysisProfile().model_dump_json(),
            tool_calls=[],
            usage={},
        )

    try:
        monkeypatch.setattr(client, "call_responses_safe", _boom)
        monkeypatch.setattr(responses_module, "call_responses_safe", _boom)
        monkeypatch.setattr(client, "call_chat_api", _fake_chat)
        monkeypatch.setattr(
            client,
            "_run_pre_extraction_analysis",
            lambda *a, **k: None,
        )
        out = client.extract_json("text")
        assert json.loads(out)["company"]
        assert chat_calls == {"count": 1}
    finally:
        config.set_api_mode(previous_mode)


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
    monkeypatch.setattr(responses_module, "call_responses_safe", _fake)
    monkeypatch.setattr(
        client,
        "call_chat_api",
        lambda *a, **k: ChatCallResult(
            content=NeedAnalysisProfile().model_dump_json(),
            tool_calls=[],
            usage={},
        ),
    )
    monkeypatch.setattr(
        client,
        "_run_pre_extraction_analysis",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("pre-analysis not expected in minimal mode")),
    )
    out = client.extract_json("text", minimal=True)
    assert "Return JSON only" in captured["messages"][0]["content"]
    assert json.loads(out)["company"]


def test_extract_json_forwards_context(monkeypatch):
    """Providing hints should be forwarded into the prompt builder."""

    st.session_state.clear()
    captured: dict[str, Any] = {}

    def _fake_build(
        text: str,
        *,
        title: str | None = None,
        company: str | None = None,
        url: str | None = None,
        locked_fields: dict[str, str] | None = None,
        insights: PreExtractionInsights | None = None,
    ) -> list[dict[str, str]]:
        captured["text"] = text
        captured["title"] = title or ""
        captured["company"] = company or ""
        captured["url"] = url or ""
        captured["locked_fields"] = locked_fields or {}
        captured["insights"] = insights
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "user"},
        ]
        captured["messages"] = messages
        return messages

    monkeypatch.setattr(client, "build_extract_messages", _fake_build)
    dummy_insights = PreExtractionInsights(summary="observed", relevant_fields=["company.name"], missing_fields=None)
    monkeypatch.setattr(
        client,
        "_run_pre_extraction_analysis",
        lambda *a, **k: dummy_insights,
    )
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
    assert captured["insights"] is dummy_insights


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
    monkeypatch.setattr(
        client,
        "_run_pre_extraction_analysis",
        lambda *a, **k: None,
    )
    out = client.extract_json("Example text")
    assert json.loads(out) == NeedAnalysisProfile().model_dump()
    assert any(
        "structured extraction" in record.getMessage() for record in caplog.records if record.levelname == "WARNING"
    )


def test_plain_text_fallback_recovers_with_repair(monkeypatch, caplog):
    """Plain-text fallbacks should attempt JSON repair before defaulting to empty payloads."""

    caplog.set_level("WARNING")
    st.session_state.clear()

    def _fail_structured(*_args: Any, **_kwargs: Any) -> str:
        raise ValueError("structured path failed")

    def _fake_chat(*_args: Any, **_kwargs: Any) -> ChatCallResult:
        return ChatCallResult(content="nonsense", tool_calls=[], usage={})

    def _parse_error(*_args: Any, **_kwargs: Any) -> NeedAnalysisProfile:
        raise ValueError("invalid json")

    def _repair_payload(*_args: Any, **_kwargs: Any) -> JsonRepairResult:
        return JsonRepairResult(
            payload={"position": {"job_title": "Recovered"}},
            status=JsonRepairStatus.REPAIRED,
            issues=["balanced"],
        )

    monkeypatch.setattr(client, "_run_pre_extraction_analysis", lambda *a, **k: None)
    monkeypatch.setattr(client, "build_extract_messages", lambda *a, **k: [{"role": "user", "content": "Job text"}])
    monkeypatch.setattr(client, "_structured_extraction", _fail_structured)
    monkeypatch.setattr(client, "call_chat_api", _fake_chat)
    monkeypatch.setattr(client, "parse_extraction", _parse_error)
    monkeypatch.setattr(client, "parse_profile_json", _repair_payload)
    monkeypatch.setattr(client, "select_model", lambda *_: "gpt-test")
    monkeypatch.setattr(client, "get_active_verbosity", lambda: None)

    result = client.extract_json("Job text")

    payload = json.loads(result)
    assert payload["position"]["job_title"] == "Recovered"
    assert payload["meta"]["extraction_fallback_active"] is True
    assert any("Plain-text fallback" in record.getMessage() for record in caplog.records)


def test_plain_text_fallback_recovers_malformed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Plain-text fallback should salvage usable JSON instead of returning an empty profile."""

    st.session_state.clear()

    def _fail_structured(*_args: Any, **_kwargs: Any) -> str:
        raise ValueError("structured path failed")

    def _fake_chat(*_args: Any, **_kwargs: Any) -> ChatCallResult:
        return ChatCallResult(
            content=(
                '{"position": {"job_title": "Engineer"}, "responsibilities": {"items": ["Lead roadmap"]}}'
                ' trailing text "unterminated'
            ),
            tool_calls=[],
            usage={},
        )

    monkeypatch.setattr(client, "_run_pre_extraction_analysis", lambda *a, **k: None)
    monkeypatch.setattr(client, "build_extract_messages", lambda *a, **k: [{"role": "user", "content": "Job text"}])
    monkeypatch.setattr(client, "_structured_extraction", _fail_structured)
    monkeypatch.setattr(client, "call_chat_api", _fake_chat)
    monkeypatch.setattr(client, "select_model", lambda *_: "gpt-test")
    monkeypatch.setattr(client, "get_active_verbosity", lambda: None)

    result = client.extract_json("Job text")

    payload = json.loads(result)
    assert payload["position"]["job_title"] == "Engineer"
    assert payload["responsibilities"]["items"] == ["Lead roadmap"]
    assert payload["meta"]["extraction_fallback_active"] is True


def test_extract_json_reapplies_locked_fields(monkeypatch):
    """Locked field hints should be merged back into the final payload."""

    locked_values = {
        "company.contact_email": "m.m@rheinbahn.de",
        "location.primary_city": "Flexible Arbeitszeiten",
    }

    def _fake_chain(payload: dict[str, Any]) -> str:
        profile = NeedAnalysisProfile()
        profile.company.contact_email = "override@example.com"
        profile.location.primary_city = "Düsseldorf"
        return profile.model_dump_json()

    monkeypatch.setattr(
        client,
        "_STRUCTURED_EXTRACTION_CHAIN",
        SimpleNamespace(invoke=_fake_chain),
    )
    monkeypatch.setattr(
        client,
        "_run_pre_extraction_analysis",
        lambda *a, **k: None,
    )
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


def test_structured_extraction_returns_validated_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """Structured extractions should return the validated payload immediately."""

    sample_data = NeedAnalysisProfile().model_dump()
    sample_json = json.dumps(sample_data, ensure_ascii=False)

    monkeypatch.setattr(client, "USE_RESPONSES_API", False)
    monkeypatch.setattr(
        client,
        "call_chat_api",
        lambda *_args, **_kwargs: ChatCallResult(content=sample_json, tool_calls=[], usage={}),
    )

    payload = {
        "messages": [{"role": "user", "content": "Extract"}],
        "model": "gpt-test",
        "reasoning_effort": None,
        "verbosity": None,
    }

    result = client._structured_extraction(payload)

    assert json.loads(result) == sample_data


def test_extract_json_skips_plain_fallback_when_structured_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`extract_json` should not invoke the plain fallback when structure parsing works."""

    st.session_state.clear()
    sample_profile = NeedAnalysisProfile().model_dump()
    structured_json = json.dumps(sample_profile, ensure_ascii=False)
    structured_calls = {"count": 0}
    fallback_calls = {"count": 0}

    def _fake_structured(payload: dict[str, Any]) -> str:
        structured_calls["count"] += 1
        assert payload["messages"] == [{"role": "user", "content": "Job text"}]
        return structured_json

    def _fail_fallback(*_args: Any, **_kwargs: Any) -> None:
        fallback_calls["count"] += 1
        raise AssertionError("Plain fallback should not run when structured output succeeds")

    class _DummySpan:
        def __enter__(self) -> "_DummySpan":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - interface only
            return None

        def set_attribute(self, *_args: Any, **_kwargs: Any) -> None:
            return None

        def set_status(self, *_args: Any, **_kwargs: Any) -> None:
            return None

        def add_event(self, *_args: Any, **_kwargs: Any) -> None:
            return None

        def record_exception(self, *_args: Any, **_kwargs: Any) -> None:
            return None

    monkeypatch.setattr(client, "_run_pre_extraction_analysis", lambda *a, **k: None)
    monkeypatch.setattr(client, "build_extract_messages", lambda *a, **k: [{"role": "user", "content": "Job text"}])
    monkeypatch.setattr(client, "select_model", lambda *_: "gpt-test")
    monkeypatch.setattr(client, "get_active_verbosity", lambda: None)
    monkeypatch.setattr(client.tracer, "start_as_current_span", lambda *a, **k: _DummySpan())
    monkeypatch.setattr(client, "_structured_extraction", _fake_structured)
    monkeypatch.setattr(client, "call_chat_api", _fail_fallback)

    result = client.extract_json("Job text")

    assert json.loads(result) == sample_profile
    assert structured_calls == {"count": 1}
    assert fallback_calls == {"count": 0}
