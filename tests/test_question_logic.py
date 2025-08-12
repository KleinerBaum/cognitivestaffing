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
