"""Tests for the LLM-first interview guide generator."""

from __future__ import annotations

import json
from typing import Any

import pytest

from llm import interview


class _FakeResponse:
    def __init__(self, content: str):
        self.content = content


@pytest.fixture()
def _valid_payload() -> dict[str, Any]:
    return {
        "metadata": {
            "language": "en",
            "heading": "Interview Guide – Engineer",
            "job_title": "Engineer",
            "audience": "general",
            "audience_label": "General interview panel",
            "tone": "Structured",
            "culture_note": "Collaboration",
        },
        "focus_areas": [
            {
                "label": "Responsibilities",
                "items": ["Deliver projects"],
            }
        ],
        "evaluation_notes": ["Probe for ownership."],
        "questions": [
            {
                "question": "Tell me about a complex project.",
                "focus": "Execution",
                "evaluation": "Look for measurable impact.",
            }
        ],
    }


def test_generate_interview_guide_returns_error_detail_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fallbacks capture the underlying exception for bilingual messaging."""

    def _raise_error(*_args: Any, **_kwargs: Any) -> Any:  # noqa: ANN401
        raise RuntimeError("schema mismatch")

    monkeypatch.setattr(interview, "call_responses", _raise_error)

    result = interview.generate_interview_guide(job_title="Engineer")

    assert result.used_fallback is True
    assert result.error_detail is not None
    assert "schema mismatch" in result.error_detail


def test_generate_interview_guide_success_has_no_error_detail(
    monkeypatch: pytest.MonkeyPatch, _valid_payload: dict[str, Any]
) -> None:
    """Successful generations do not expose fallback errors."""

    def _return_valid(*_args: Any, **_kwargs: Any) -> Any:  # noqa: ANN401
        return _FakeResponse(json.dumps(_valid_payload))

    monkeypatch.setattr(interview, "call_responses", _return_valid)

    result = interview.generate_interview_guide(job_title="Engineer", lang="en")

    assert result.used_fallback is False
    assert result.error_detail is None
