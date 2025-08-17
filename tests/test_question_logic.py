from typing import Any
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent.parent))
from question_logic import (
    CRITICAL_FIELDS,
    _rag_suggestions,
    generate_followup_questions,
)


def test_generate_followup_questions() -> None:
    """Basic smoke test for follow-up question generation."""
    out = generate_followup_questions(
        {"company.name": "ACME"}, num_questions=1, use_rag=False
    )
    assert len(out) == 1
    q = out[0]
    assert q["field"] in CRITICAL_FIELDS
    assert q["priority"] in {"critical", "normal"}


def test_role_specific_extra_question(monkeypatch) -> None:
    """Role classification should add role-specific questions."""
    monkeypatch.setattr(
        "question_logic.classify_occupation",
        lambda jt, lang="en": {"group": "Software developers"},
    )
    monkeypatch.setattr("question_logic.CRITICAL_FIELDS", {"position.job_title"})
    out = generate_followup_questions(
        {"position.job_title": "Backend Developer"}, use_rag=False
    )
    assert any(q["field"] == "programming_languages" for q in out)


def test_yes_no_default(monkeypatch) -> None:
    """Yes/no fields default to 'No' when treated as missing."""
    monkeypatch.setattr(
        "question_logic.CRITICAL_FIELDS", {"employment.visa_sponsorship"}
    )
    out = generate_followup_questions({}, num_questions=1, use_rag=False)
    assert out == [
        {
            "field": "employment.visa_sponsorship",
            "question": out[0]["question"],
            "priority": "critical",
            "suggestions": [],
            "prefill": "No",
        }
    ]


def test_language_level_question(monkeypatch) -> None:
    """Missing English level should trigger a specific question."""
    monkeypatch.setattr(
        "question_logic.CRITICAL_FIELDS", {"requirements.language_level_english"}
    )
    out = generate_followup_questions({}, num_questions=1, use_rag=False)
    assert out[0]["field"] == "requirements.language_level_english"
    assert "English" in out[0]["question"]


def test_rag_suggestions_merge(monkeypatch) -> None:
    """RAG suggestions should populate the suggestions list."""
    monkeypatch.setattr("question_logic.CRITICAL_FIELDS", {"location.primary_city"})
    monkeypatch.setattr(
        "question_logic._rag_suggestions",
        lambda *a, **k: {"location.primary_city": ["Berlin"]},
    )
    monkeypatch.setattr("question_logic.OPENAI_API_KEY", "test")
    out = generate_followup_questions({}, num_questions=1, use_rag=True)
    assert out[0]["field"] == "location.primary_city"
    assert out[0]["suggestions"] == ["Berlin"]


def test_new_field_triggers_question(monkeypatch) -> None:
    """New schema fields should yield follow-up questions when missing."""
    monkeypatch.setattr(
        "question_logic.CRITICAL_FIELDS", {"contacts.hiring_manager.phone"}
    )
    out = generate_followup_questions({}, num_questions=1, use_rag=False)
    assert out[0]["field"] == "contacts.hiring_manager.phone"
    assert "phone" in out[0]["question"].lower()


def test_rag_suggestions_tool_payload(monkeypatch) -> None:
    """_rag_suggestions should pass nested file_search tool payload."""

    captured: dict[str, Any] = {}

    class _Fake:
        content = "{}"

    def fake_call(messages, **kwargs):
        captured["tools"] = kwargs.get("tools")
        captured["tool_choice"] = kwargs.get("tool_choice")
        captured["extra"] = kwargs.get("extra")
        return _Fake()

    monkeypatch.setattr("question_logic.call_chat_api", fake_call)

    _rag_suggestions("Engineer", "Tech", ["location"], vector_store_id="vs123")

    assert captured["tools"] == [{"type": "custom", "name": "file_search"}]
    assert captured["tool_choice"] == "auto"
    assert captured["extra"] == {
        "tool_resources": {"file_search": {"vector_store_ids": ["vs123"]}}
    }
