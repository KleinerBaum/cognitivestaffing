from question_logic import CRITICAL_FIELDS, generate_followup_questions


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


def test_rag_suggestions_merge(monkeypatch) -> None:
    """RAG suggestions should populate the suggestions list."""
    monkeypatch.setattr("question_logic.CRITICAL_FIELDS", {"location.primary_city"})
    monkeypatch.setattr(
        "question_logic._rag_suggestions",
        lambda *a, **k: {"location.primary_city": ["Berlin"]},
    )
    out = generate_followup_questions({}, num_questions=1, use_rag=True)
    assert out[0]["field"] == "location.primary_city"
    assert out[0]["suggestions"] == ["Berlin"]
