import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parent.parent))
from question_logic import (  # noqa: E402
    CRITICAL_FIELDS,
    _rag_suggestions,
    ask_followups,
    generate_followup_questions,
)
from openai_utils import ChatCallResult  # noqa: E402
from constants.keys import StateKeys  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_session_state() -> None:
    st.session_state.clear()


def test_generate_followup_questions() -> None:
    """Basic smoke test for follow-up question generation."""
    out = generate_followup_questions({"company.name": "ACME"}, num_questions=1, use_rag=False)
    assert len(out) == 1
    q = out[0]
    assert q["field"] in CRITICAL_FIELDS
    assert q["priority"] in {"critical", "normal"}


def test_role_specific_questions_from_esco_state(monkeypatch) -> None:
    """Role-specific prompts should activate when ESCO provides a group."""

    monkeypatch.setattr("question_logic.CRITICAL_FIELDS", {"position.job_title"})
    st.session_state[StateKeys.UI_ESCO_OCCUPATION_OPTIONS] = [
        {
            "preferredLabel": "Software developers",
            "group": "Information and communications technology professionals",
            "uri": "offline://ict",
        }
    ]
    st.session_state[StateKeys.ESCO_SELECTED_OCCUPATIONS] = [
        {
            "preferredLabel": "Software developers",
            "group": "Information and communications technology professionals",
            "uri": "offline://ict",
        }
    ]
    st.session_state[StateKeys.ESCO_SKILLS] = ["Python", "Version control"]

    out = generate_followup_questions({"position": {"job_title": "Backend Developer"}}, use_rag=False)
    fields = {q["field"] for q in out}
    assert "requirements.tools_and_technologies" in fields
    tech_question = next(q for q in out if q["field"] == "requirements.tools_and_technologies")
    assert "Python" in tech_question["suggestions"]


def test_esco_missing_skills_trigger_followup(monkeypatch) -> None:
    """Missing ESCO skills should trigger a critical follow-up even with data."""

    monkeypatch.setattr(
        "question_logic.CRITICAL_FIELDS",
        {"requirements.hard_skills_required"},
    )
    st.session_state[StateKeys.UI_ESCO_OCCUPATION_OPTIONS] = [
        {
            "preferredLabel": "Software developers",
            "group": "Information and communications technology professionals",
            "uri": "offline://ict",
        }
    ]
    st.session_state[StateKeys.ESCO_SELECTED_OCCUPATIONS] = [
        {
            "preferredLabel": "Software developers",
            "group": "Information and communications technology professionals",
            "uri": "offline://ict",
        }
    ]
    st.session_state[StateKeys.ESCO_SKILLS] = ["Python", "Data analysis"]

    profile = {
        "position": {"job_title": "Data Analyst"},
        "requirements": {"hard_skills_required": ["Python"]},
    }

    out = generate_followup_questions(profile, use_rag=False)
    hard_skill_question = next(q for q in out if q["field"] == "requirements.hard_skills_required")

    assert hard_skill_question["priority"] == "critical"
    assert hard_skill_question["suggestions"] == ["Data analysis"]
    assert st.session_state[StateKeys.ESCO_MISSING_SKILLS] == ["Data analysis"]


def test_yes_no_default(monkeypatch) -> None:
    """Yes/no fields default to 'No' when treated as missing."""
    monkeypatch.setattr("question_logic.CRITICAL_FIELDS", {"employment.visa_sponsorship"})
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
    monkeypatch.setattr("question_logic.CRITICAL_FIELDS", {"requirements.language_level_english"})
    out = generate_followup_questions({}, num_questions=1, use_rag=False)
    assert out[0]["field"] == "requirements.language_level_english"
    assert "English" in out[0]["question"]


def test_missing_city_triggers_followup() -> None:
    """Omitting the city should yield a critical follow-up question."""
    assert "location.primary_city" in CRITICAL_FIELDS

    profile = {
        "company": {"name": "ACME"},
        "position": {"job_title": "Engineer", "role_summary": "Build products"},
        "location": {"country": "DE"},
        "requirements": {
            "hard_skills_required": ["Python"],
            "soft_skills_required": ["Teamwork"],
        },
    }

    out = generate_followup_questions(profile, use_rag=False)
    city_question = next(q for q in out if q["field"] == "location.primary_city")
    assert city_question["priority"] == "critical"
    assert "city" in city_question["question"].lower()


def test_missing_contact_email_triggers_followup() -> None:
    """Missing company contact email should raise a critical follow-up."""

    assert "company.contact_email" in CRITICAL_FIELDS

    profile = {
        "company": {"name": "ACME", "contact_name": "Max"},
        "position": {"job_title": "Engineer", "role_summary": "Build products"},
        "location": {"country": "DE", "primary_city": "Berlin"},
        "responsibilities": {"items": ["Build"]},
        "requirements": {
            "hard_skills_required": ["Python"],
            "soft_skills_required": ["Teamwork"],
        },
    }

    out = generate_followup_questions(profile, use_rag=False)
    email_question = next(q for q in out if q["field"] == "company.contact_email")
    assert email_question["priority"] == "critical"
    assert "email" in email_question["question"].lower()


def test_rag_suggestions_merge(monkeypatch) -> None:
    """RAG suggestions should populate the suggestions list."""
    monkeypatch.setattr("question_logic.CRITICAL_FIELDS", {"location.primary_city"})
    monkeypatch.setattr(
        "question_logic._rag_suggestions",
        lambda *a, **k: {"location.primary_city": ["Berlin"]},
    )
    monkeypatch.setattr("question_logic.is_llm_enabled", lambda: True)
    out = generate_followup_questions({}, num_questions=1, use_rag=True)
    assert out[0]["field"] == "location.primary_city"
    assert out[0]["suggestions"] == ["Berlin"]


def test_new_field_triggers_question(monkeypatch) -> None:
    """New schema fields should yield follow-up questions when missing."""
    monkeypatch.setattr("question_logic.CRITICAL_FIELDS", {"contacts.hiring_manager.phone"})
    out = generate_followup_questions({}, num_questions=1, use_rag=False)
    assert out[0]["field"] == "contacts.hiring_manager.phone"
    assert "phone" in out[0]["question"].lower()


def test_rag_suggestions_tool_payload(monkeypatch) -> None:
    """_rag_suggestions should pass nested file_search tool payload."""

    captured: dict[str, Any] = {}

    def fake_call(messages, **kwargs):
        captured["tools"] = kwargs.get("tools")
        captured["tool_choice"] = kwargs.get("tool_choice")
        captured["extra"] = kwargs.get("extra")
        return ChatCallResult("{}", [], {})

    monkeypatch.setattr("question_logic.call_chat_api", fake_call)

    _rag_suggestions("Engineer", "Tech", ["location"], vector_store_id="vs123")

    assert captured["tools"] == [
        {
            "type": "file_search",
            "name": "file_search",
            "vector_store_ids": ["vs123"],
            "file_search": {"vector_store_ids": ["vs123"]},
        }
    ]
    assert captured["tool_choice"] == "auto"
    assert captured.get("extra") in (None, {})


def test_rag_suggestions_skipped_flag(monkeypatch) -> None:
    """When no vector store is configured the skip flag should be recorded."""

    monkeypatch.setattr("question_logic.RAG_VECTOR_STORE_ID", None)
    out = _rag_suggestions("Engineer", "Tech", ["location"], vector_store_id=None)

    assert out == {}
    assert st.session_state[StateKeys.RAG_CONTEXT_SKIPPED] is True


def test_rag_suggestions_clears_skip_flag(monkeypatch) -> None:
    """Providing a vector store should unset the skip flag before execution."""

    def fake_call(messages, **_kwargs):
        return ChatCallResult("{}", [], {})

    monkeypatch.setattr("question_logic.call_chat_api", fake_call)
    monkeypatch.setattr("question_logic.RAG_VECTOR_STORE_ID", "vs123")
    st.session_state[StateKeys.RAG_CONTEXT_SKIPPED] = True

    _rag_suggestions("Engineer", "Tech", ["location"], vector_store_id="vs456")

    assert st.session_state[StateKeys.RAG_CONTEXT_SKIPPED] is False


def test_rag_suggestions_failure(monkeypatch) -> None:
    """Failures during RAG retrieval should warn and return empty suggestions."""

    def fail_call(*_a, **_k):
        raise RuntimeError("boom")

    warnings: dict[str, str] = {}
    monkeypatch.setattr("question_logic.call_chat_api", fail_call)
    monkeypatch.setattr(
        "question_logic.logger",
        types.SimpleNamespace(warning=lambda msg, *a: warnings.setdefault("log", msg)),
    )

    def capture(msg):
        warnings["ui"] = str(msg)

    monkeypatch.setattr("question_logic.st.warning", capture)

    out = _rag_suggestions("Engineer", "Tech", ["location"], vector_store_id="vs123")

    assert out == {}
    assert "ui" in warnings


def test_followup_normalizes_missing_suggestions(monkeypatch) -> None:
    """ask_followups should backfill missing suggestions arrays."""

    class _FakeMessage:
        def __init__(self) -> None:
            self.content = json.dumps(
                {
                    "questions": [
                        {
                            "field": "position.job_title",
                            "question": "What is the job title?",
                            "priority": "critical",
                        }
                    ]
                }
            )

    monkeypatch.setattr("question_logic.call_chat_api", lambda *a, **k: _FakeMessage())

    out = ask_followups({})

    assert out == {
        "questions": [
            {
                "field": "position.job_title",
                "question": "What is the job title?",
                "priority": "critical",
                "suggestions": [],
            }
        ]
    }


def test_generate_followups_skip_answered(monkeypatch) -> None:
    """Fields marked as answered should not be re-asked."""

    monkeypatch.setattr("question_logic.CRITICAL_FIELDS", {"position.job_title"})
    data = {
        "position": {"job_title": ""},
        "meta": {"followups_answered": ["position.job_title"]},
    }

    out = generate_followup_questions(data, num_questions=2, use_rag=False)

    assert out == []


def test_generate_followups_salary_implausible(monkeypatch) -> None:
    """Implausible salary values should trigger a combined salary range question."""

    monkeypatch.setattr(
        "question_logic.CRITICAL_FIELDS",
        {"compensation.salary_min", "compensation.salary_max"},
    )
    data = {"compensation": {"salary_min": 0, "salary_max": "0", "currency": "EUR"}}

    out = generate_followup_questions(data, use_rag=False)

    assert out[0]["field"] == "compensation.salary_range"
    assert "salary" in out[0]["question"].lower()
    assert "unusual" in out[0]["question"].lower()


def test_generate_followups_include_esco_suggestions(monkeypatch) -> None:
    """ESCO suggestions should augment missing skill fields."""

    monkeypatch.setattr("question_logic.CRITICAL_FIELDS", {"requirements.hard_skills_required"})

    data = {
        "position": {"job_title": "Backend Developer"},
        "requirements": {"hard_skills_required": []},
    }

    out = generate_followup_questions(data, use_rag=False, lang="en")

    assert out[0]["field"] == "requirements.hard_skills_required"
    assert "Python" in out[0]["suggestions"]


def test_generate_followups_benefit_defaults(monkeypatch) -> None:
    """Benefit follow-ups should provide default suggestions when no API key is set."""

    monkeypatch.setattr("question_logic.CRITICAL_FIELDS", {"compensation.benefits"})
    monkeypatch.setattr("question_logic.is_llm_enabled", lambda: False)

    data = {
        "position": {"job_title": "Engineer"},
        "compensation": {"benefits": []},
    }

    out = generate_followup_questions(data, use_rag=False, lang="en")

    assert out[0]["field"] == "compensation.benefits"
    assert out[0]["suggestions"]
