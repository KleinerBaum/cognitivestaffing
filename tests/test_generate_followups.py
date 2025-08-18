import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from models.need_analysis import NeedAnalysisProfile  # noqa: E402
from questions.generate import generate_followup_questions  # noqa: E402


def test_generate_followups_wrapper(monkeypatch):
    captured = {}

    def fake_generate(data, num_questions=None, lang="en", use_rag=True):
        captured.update(
            {
                "data": data,
                "num_questions": num_questions,
                "lang": lang,
                "use_rag": use_rag,
            }
        )
        return [
            {"field": "company.name", "question": "Company name?"},
            {"field": "location.primary_city", "question": "Location?"},
        ]

    monkeypatch.setattr(
        "questions.generate._generate_followup_questions", fake_generate
    )

    jd = NeedAnalysisProfile()
    questions = generate_followup_questions(
        jd, num_questions=2, lang="de", use_rag=False
    )

    assert questions == ["Company name?", "Location?"]
    assert captured["num_questions"] == 2
    assert captured["lang"] == "de"
    assert captured["use_rag"] is False


def test_generate_followups_wrapper_empty(monkeypatch):
    def fake_generate(data, num_questions=None, lang="en", use_rag=True):
        return []

    monkeypatch.setattr(
        "questions.generate._generate_followup_questions", fake_generate
    )

    jd = NeedAnalysisProfile()
    assert generate_followup_questions(jd) == []
