import os
import sys
import json

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from question_logic import CRITICAL_FIELDS, generate_followup_questions  # noqa: E402


def test_generate_followup_questions(monkeypatch):
    """Ensure follow-up questions are parsed from model output."""

    def fake_call_chat_api(
        messages, temperature=0.0, max_tokens=0, model=None
    ) -> str:  # noqa: E501
        return '[{"field": "salary_range", "question": ' '"What is the salary range?"}]'

    monkeypatch.setattr("question_logic.call_chat_api", fake_call_chat_api)
    monkeypatch.setattr("question_logic.OPENAI_API_KEY", "")
    questions = generate_followup_questions({"company_name": "ACME"})
    assert questions == [
        {
            "field": "salary_range",
            "question": "What is the salary range?",
            "priority": "critical",
            "suggestions": [],
            "prefill": "",
        }
    ]


def test_role_specific_payload(monkeypatch):
    """Classification should add role-specific fields to the payload."""

    captured = {}

    def fake_call_chat_api(
        messages, temperature=0.0, max_tokens=0, model=None
    ) -> str:  # noqa: E501
        captured["payload"] = messages[1]["content"]
        return "[]"

    def fake_classify(job_title, lang="en"):
        return {
            "preferredLabel": "Software developer",
            "group": "Software developers",
            "uri": "http://example.com/occ",
        }

    def fake_get_skills(uri, lang="en"):
        return ["Project management"]

    monkeypatch.setattr("question_logic.call_chat_api", fake_call_chat_api)
    monkeypatch.setattr("question_logic.classify_occupation", fake_classify)
    monkeypatch.setattr("question_logic.get_essential_skills", fake_get_skills)
    monkeypatch.setattr("question_logic.OPENAI_API_KEY", "")

    generate_followup_questions({"job_title": "Software engineer"})

    payload_json = captured["payload"].split("Context:\n", 1)[1]
    data = json.loads(payload_json)
    assert "programming_languages" in data["current"]
    assert data["occupation"]["group"] == "Software developers"
    assert data["occupation"]["preferredLabel"] == "Software developer"
    assert data["missing_esco_skills"] == ["Project management"]


def test_role_specific_extra_question(monkeypatch):
    """Role-specific questions should be appended automatically."""

    def fake_call_chat_api(
        messages, temperature=0.0, max_tokens=0, model=None
    ) -> str:  # noqa: E501
        return "[]"

    def fake_classify(job_title, lang="en"):
        return {"group": "Software developers"}

    monkeypatch.setattr("question_logic.call_chat_api", fake_call_chat_api)
    monkeypatch.setattr("question_logic.classify_occupation", fake_classify)
    monkeypatch.setattr("question_logic.OPENAI_API_KEY", "")

    out = generate_followup_questions({"job_title": "Backend Developer"})
    assert any(q["field"] == "programming_languages" for q in out)


def test_optional_field_cap(monkeypatch):
    """Missing optional fields should not exceed the minimum question cap."""

    captured = {}

    def fake_call_chat_api(
        messages, temperature=0.0, max_tokens=0, model=None
    ) -> str:  # noqa: E501
        captured["payload"] = messages[1]["content"]
        return "[]"

    monkeypatch.setattr("question_logic.call_chat_api", fake_call_chat_api)
    monkeypatch.setattr("question_logic.OPENAI_API_KEY", "")

    extracted = {f: "x" for f in CRITICAL_FIELDS}
    generate_followup_questions(extracted)

    payload_json = captured["payload"].split("Context:\n", 1)[1]
    data = json.loads(payload_json)
    assert data["rules"]["max_questions"] == 3


def test_qualification_split(monkeypatch):
    """Missing qualifications should trigger split sub-questions."""

    captured = {}

    def fake_call_chat_api(
        messages, temperature=0.0, max_tokens=0, model=None
    ) -> str:  # noqa: E501
        captured["payload"] = messages[1]["content"]
        return "[]"

    monkeypatch.setattr("question_logic.call_chat_api", fake_call_chat_api)
    monkeypatch.setattr("question_logic.OPENAI_API_KEY", "")

    extracted = {f: "x" for f in CRITICAL_FIELDS if f != "qualifications"}
    generate_followup_questions(extracted)

    payload_json = captured["payload"].split("Context:\n", 1)[1]
    data = json.loads(payload_json)
    assert data["rules"]["max_questions"] == 5
    assert data["rules"]["split_fields"] == {
        "qualifications": ["education", "experience"]
    }


def test_prefill_from_rag(monkeypatch):
    """First RAG suggestion should populate prefill value."""

    def fake_call_chat_api(
        messages, temperature=0.0, max_tokens=0, model=None
    ) -> str:  # noqa: E501
        return '[{"field": "location", "question": "Location?"}]'

    monkeypatch.setattr("question_logic.call_chat_api", fake_call_chat_api)
    monkeypatch.setattr("question_logic.OPENAI_API_KEY", "")
    monkeypatch.setattr(
        "question_logic._rag_suggestions", lambda *a, **k: {"location": ["Berlin"]}
    )
    out = generate_followup_questions({"company_name": "ACME"})
    assert out == [
        {
            "field": "location",
            "question": "Location?",
            "priority": "critical",
            "suggestions": ["Berlin"],
            "prefill": "Berlin",
        }
    ]


def test_yes_no_default(monkeypatch):
    """Yes/no fields default to 'Not specified' when empty."""

    def fake_call_chat_api(
        messages, temperature=0.0, max_tokens=0, model=None
    ) -> str:  # noqa: E501
        return '[{"field": "visa_sponsorship", "question": "Visa sponsorship?"}]'

    monkeypatch.setattr("question_logic.call_chat_api", fake_call_chat_api)
    monkeypatch.setattr("question_logic.OPENAI_API_KEY", "")
    out = generate_followup_questions({"company_name": "ACME"})
    assert out == [
        {
            "field": "visa_sponsorship",
            "question": "Visa sponsorship?",
            "priority": "normal",
            "suggestions": [],
            "prefill": "Not specified",
        }
    ]


def test_static_suggestions_merge(monkeypatch):
    """Static field suggestions should be merged with RAG results."""

    def fake_call_chat_api(
        messages, temperature=0.0, max_tokens=0, model=None
    ) -> str:  # noqa: E501
        return '[{"field": "programming_languages", "question": "Languages?"}]'

    monkeypatch.setattr("question_logic.call_chat_api", fake_call_chat_api)
    monkeypatch.setattr("question_logic.OPENAI_API_KEY", "")
    monkeypatch.setattr(
        "question_logic.classify_occupation",
        lambda jt, lang="en": {"group": "Software developers"},
    )
    monkeypatch.setattr("question_logic.get_essential_skills", lambda *a, **k: [])
    monkeypatch.setattr(
        "question_logic._rag_suggestions",
        lambda *a, **k: {"programming_languages": ["Python", "Elm"]},
    )
    out = generate_followup_questions({"job_title": "Backend Developer"})
    item = next(q for q in out if q["field"] == "programming_languages")
    assert item["suggestions"][0:2] == ["Python", "Elm"]
    assert "Java" in item["suggestions"]
    assert item["suggestions"].count("Python") == 1
