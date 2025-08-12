import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.schema import VacalyserJD  # noqa: E402
from questions.generate import generate_followup_questions  # noqa: E402


def test_generate_followups_wrapper(monkeypatch):
    def fake_generate(data, num_questions=None, lang="en", use_rag=True):
        return [
            {"field": "company_name", "question": "Company name?"},
            {"field": "location", "question": "Location?"},
        ]

    monkeypatch.setattr(
        "questions.generate._generate_followup_questions", fake_generate
    )

    jd = VacalyserJD(job_title="Dev")
    questions = generate_followup_questions(jd)
    assert questions == ["Company name?", "Location?"]


def test_generate_followups_wrapper_empty(monkeypatch):
    def fake_generate(data, num_questions=None, lang="en", use_rag=True):
        return []

    monkeypatch.setattr(
        "questions.generate._generate_followup_questions", fake_generate
    )

    jd = VacalyserJD(job_title="Dev")
    assert generate_followup_questions(jd) == []
