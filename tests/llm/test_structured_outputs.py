import pytest

from config import ModelTask
import llm.openai_responses as responses
from models.interview_guide import InterviewGuide
from llm.openai_responses import build_json_schema_format, call_responses


def test_build_json_schema_format_includes_name_and_schema() -> None:
    fmt = build_json_schema_format(name="JobProfile", schema={"type": "object"})
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["name"] == "JobProfile"
    assert fmt["json_schema"]["schema"] == {
        "type": "object",
        "additionalProperties": False,
        "$schema": "http://json-schema.org/draft-07/schema#",
    }
    assert fmt["json_schema"]["strict"] is True


def test_interview_guide_schema_marks_focus_area_label_required() -> None:
    fmt = build_json_schema_format(name="interviewGuide", schema=InterviewGuide.model_json_schema())

    focus_schema = fmt["schema"]["$defs"]["InterviewGuideFocusArea"]

    assert focus_schema["required"] == ["label", "items"]


def test_call_responses_invokes_client(monkeypatch: pytest.MonkeyPatch) -> None:
    payload_box: dict[str, dict] = {}
    usage_updates: list[dict] = []

    class _DummyResponses:
        def create(self, **payload):
            payload_box["payload"] = payload
            return object()

    class _DummyClient:
        def __init__(self) -> None:
            self.responses = _DummyResponses()

    monkeypatch.setattr(responses, "get_client", lambda: _DummyClient())
    monkeypatch.setattr(responses, "_extract_output_text", lambda _r: "{}")
    monkeypatch.setattr(responses, "_extract_response_id", lambda _r: "resp")
    monkeypatch.setattr(responses, "_extract_usage_block", lambda _r: {"input_tokens": 5})
    monkeypatch.setattr(responses, "_normalise_usage", lambda usage: usage)
    monkeypatch.setattr(responses, "_coerce_token_count", lambda value: int(value))
    monkeypatch.setattr(responses, "_update_usage_counters", lambda usage, task=None: usage_updates.append(dict(usage)))
    monkeypatch.setattr(responses, "model_supports_temperature", lambda model: True)
    monkeypatch.setattr(responses, "model_supports_reasoning", lambda model: False)

    fmt = build_json_schema_format(name="Profile", schema={"type": "object"})
    result = call_responses(
        [{"role": "user", "content": "hi"}],
        model="gpt-4o-mini",
        response_format=fmt,
        temperature=0.1,
        max_completion_tokens=256,
        task=ModelTask.EXTRACTION,
    )

    assert result.content == "{}"
    assert result.response_id == "resp"
    assert result.usage == {"input_tokens": 5}
    assert usage_updates == [{"input_tokens": 5}]

    payload = payload_box["payload"]
    assert payload["model"] == "gpt-4o-mini"
    assert payload["temperature"] == pytest.approx(0.1)
    assert payload["max_output_tokens"] == 256
    format_payload = payload["text"]["format"]
    assert format_payload["type"] == "json_schema"
    assert format_payload["name"] == "Profile"
    assert format_payload["schema"] == {
        "type": "object",
        "additionalProperties": False,
        "$schema": "http://json-schema.org/draft-07/schema#",
    }
    assert format_payload.get("strict") is True
    assert payload["input"][0]["role"] == "user"
