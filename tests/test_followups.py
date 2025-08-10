import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from core.schema import VacalyserJD  # noqa: E402
from questions.generate import generate_followup_questions  # noqa: E402


def test_missing_detector_categories(monkeypatch) -> None:
    captured = {}

    def fake_call_chat_api(messages, temperature=0.0, max_tokens=0):
        captured["prompt"] = messages[1]["content"]
        return "[]"

    monkeypatch.setattr("questions.generate.call_chat_api", fake_call_chat_api)
    monkeypatch.setattr(
        "questions.generate.classify_occupation", lambda *args, **kwargs: {}
    )
    monkeypatch.setattr(
        "questions.generate.get_essential_skills", lambda *args, **kwargs: []
    )

    jd = VacalyserJD(job_title="Dev", responsibilities=["Code"])
    generate_followup_questions(jd)

    prompt = captured["prompt"]
    missing = prompt.split("fields: ", 1)[1].split(". Return", 1)[0]
    assert "responsibilities" not in missing
    assert "hard_skills" in missing
    assert "company_name" in missing
