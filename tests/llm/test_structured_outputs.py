from __future__ import annotations

from types import SimpleNamespace

import pytest

import config.models as model_config
from config import APIMode
from config.models import ModelTask
from llm.openai_responses import build_json_schema_format, call_responses
from models.interview_guide import InterviewGuide


def test_build_json_schema_format_includes_name_and_schema() -> None:
    fmt = build_json_schema_format(name="JobProfile", schema={"type": "object"})
    assert fmt["type"] == "json_schema"
    payload = fmt["json_schema"]
    assert payload["name"] == "JobProfile"
    assert payload["strict"] is True
    assert payload["schema"]["type"] == "object"


def test_interview_guide_schema_marks_focus_area_label_required() -> None:
    fmt = build_json_schema_format(name="interviewGuide", schema=InterviewGuide.model_json_schema())
    focus_schema = fmt["json_schema"]["schema"]["$defs"]["InterviewGuideFocusArea"]
    assert "label" in focus_schema["required"]
    assert "items" in focus_schema["required"]


def test_call_responses_invokes_responses_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _fake_call_chat_api(messages, **kwargs):  # type: ignore[no-untyped-def]
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return SimpleNamespace(content="{}", usage={"input_tokens": 5}, response_id="resp", raw_response={})

    monkeypatch.setattr("llm.openai_responses.call_chat_api", _fake_call_chat_api)

    fmt = build_json_schema_format(name="Profile", schema={"type": "object"})
    result = call_responses(
        [{"role": "user", "content": "hi"}],
        model=model_config.GPT51_NANO,
        response_format=fmt,
        temperature=0.1,
        max_completion_tokens=256,
        task=ModelTask.EXTRACTION,
    )

    assert result.content == "{}"
    assert result.response_id == "resp"
    assert captured["kwargs"]["api_mode"] == APIMode.RESPONSES
    assert captured["kwargs"]["allow_legacy_fallback"] is False
