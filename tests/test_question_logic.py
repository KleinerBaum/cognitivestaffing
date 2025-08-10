import os
import sys
import json

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from question_logic import generate_followup_questions  # noqa: E402


def test_generate_followup_questions(monkeypatch):
    """Ensure follow-up questions are parsed from model output."""

    def fake_call_chat_api(
        messages, temperature=0.0, max_tokens=0, model=None
    ) -> str:  # noqa: E501
        return '[{"field": "salary_range", "question": ' '"What is the salary range?"}]'

    monkeypatch.setattr("question_logic.call_chat_api", fake_call_chat_api)
    questions = generate_followup_questions({"company_name": "ACME"})
    assert questions == [
        {"field": "salary_range", "question": "What is the salary range?"}
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
        return {"preferredLabel": "Software developer", "group": "Software developers"}

    monkeypatch.setattr("question_logic.call_chat_api", fake_call_chat_api)
    monkeypatch.setattr("question_logic.classify_occupation", fake_classify)

    generate_followup_questions({"job_title": "Software engineer"})

    payload_json = captured["payload"].split("Current data:\n", 1)[1]
    data = json.loads(payload_json)
    assert "programming_languages" in data
    assert data["esco_group"] == "Software developers"
    assert data["esco_occupation"] == "Software developer"
