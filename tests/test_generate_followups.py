import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.schema import VacalyserJD, ALL_FIELDS, LIST_FIELDS  # noqa: E402
from questions.generate import generate_followup_questions  # noqa: E402


def test_generate_followups(monkeypatch):
    def fake_call_chat_api(messages, temperature=0.0, max_tokens=0):
        return '["Company name?", "Location?", "Salary?"]'

    def fake_classify(job_title, lang="en"):
        return {"preferredLabel": "Developer", "group": "Software", "uri": "u"}

    def fake_skills(uri, lang="en"):
        return ["Python", "Teamwork"]

    monkeypatch.setattr(
        "questions.generate.call_chat_api", fake_call_chat_api
    )
    monkeypatch.setattr(
        "questions.generate.classify_occupation", fake_classify
    )
    monkeypatch.setattr(
        "questions.generate.get_essential_skills", fake_skills
    )

    jd = VacalyserJD(job_title="Dev")
    questions = generate_followup_questions(jd)
    assert questions == [
        "Company name?",
        "Location?",
        "Salary?",
        "What are the main responsibilities for this role?",
        "Does the role require any of the following skills: Python, Teamwork?",
    ]


def test_generate_followups_complete(monkeypatch):
    data = {}
    for field in ALL_FIELDS:
        if field in LIST_FIELDS:
            data[field] = ["x"]
        else:
            data[field] = "x"
    jd = VacalyserJD(**data)

    def fail_call(*args, **kwargs):  # pragma: no cover
        raise AssertionError("should not call")

    monkeypatch.setattr("questions.generate.call_chat_api", fail_call)
    assert generate_followup_questions(jd) == []
