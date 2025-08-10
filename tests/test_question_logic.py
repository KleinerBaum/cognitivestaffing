import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from question_logic import generate_followup_questions  # noqa: E402


def test_generate_followup_questions(monkeypatch):
    """Ensure follow-up questions are parsed from model output."""

    def fake_call_chat_api(messages, temperature=0.0, max_tokens=0, model=None) -> str:  # noqa: E501
        return (
            "[{\"field\": \"salary_range\", \"question\": "
            "\"What is the salary range?\"}]"
        )

    monkeypatch.setattr(
        "question_logic.call_chat_api", fake_call_chat_api
    )
    questions = generate_followup_questions({"company_name": "ACME"})
    assert questions == [
        {"field": "salary_range", "question": "What is the salary range?"}
    ]
