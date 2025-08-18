"""Legacy wrapper for the unified follow-up question generator."""

from __future__ import annotations

from typing import List, Optional

from models.need_analysis import NeedAnalysisProfile

from question_logic import (
    generate_followup_questions as _generate_followup_questions,
)


def generate_followup_questions(
    jd: NeedAnalysisProfile,
    num_questions: Optional[int] = None,
    lang: str = "en",
    use_rag: bool = True,
) -> List[str]:
    """Return follow-up questions as simple strings.

    This thin wrapper delegates to
    :func:`question_logic.generate_followup_questions`, which returns rich
    question objects including priority levels and suggestions. For backwards
    compatibility, only the ``question`` text is exposed here while the full
    set of parameters is forwarded to the underlying function.

    Args:
        jd: Parsed job description data.
        num_questions: Optional maximum number of questions to return.
        lang: Language for generated questions.
        use_rag: Whether to use RAG-based suggestions.

    Returns:
        List of follow-up question strings.
    """

    items = _generate_followup_questions(
        jd.model_dump(),
        num_questions=num_questions,
        lang=lang,
        use_rag=use_rag,
    )
    return [it["question"] for it in items if it.get("question")]
