import json
from typing import Any

import pytest

from openai_utils.api import ChatCallResult
from pipelines import team_advice as team_advice_pipeline
from llm import team_advisor


class _StubPromptRegistry:
    def format(self, *_: Any, **__: Any) -> str:  # noqa: D401
        """Return a deterministic prompt string for tests."""

        return "prompt"


def test_team_advice_uses_text_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_call(messages: list[dict[str, Any]], **kwargs: Any) -> ChatCallResult:  # noqa: ARG001
        captured.update(kwargs)
        payload = {
            "assistant_message": "Reports to CTO",
            "reporting_line_suggestion": "CTO",
            "direct_reports_suggestion": 2,
            "follow_up_question": "Is a dotted-line report needed?",
        }
        return ChatCallResult(content=json.dumps(payload), tool_calls=[], usage={})

    monkeypatch.setattr(team_advisor, "call_chat_api", fake_call)
    monkeypatch.setattr(team_advisor, "get_model_for", lambda *_, **__: "model-team-advice")
    monkeypatch.setattr(team_advisor, "prompt_registry", _StubPromptRegistry())

    advice = team_advisor.advise_team_structure(None, {}, lang="en")

    assert advice.reporting_line == "CTO"
    assert advice.direct_reports == 2
    assert captured.get("json_schema") is None
    assert captured.get("use_response_format") is False


def test_team_advice_pipeline_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(team_advice_pipeline, "advise_team_structure", lambda *_, **__: (_ for _ in ()).throw(RuntimeError()))

    advice = team_advice_pipeline.generate_team_advice({}, lang="en")

    assert advice.message
    assert advice.reporting_line is None
