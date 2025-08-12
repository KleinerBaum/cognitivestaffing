"""Legacy wrapper for the unified follow-up question generator."""

from __future__ import annotations

from typing import List

from core.schema import VacalyserJD

from question_logic import (
    generate_followup_questions as _generate_followup_questions,
)


def generate_followup_questions(jd: VacalyserJD, lang: str = "en") -> List[str]:
    """Return follow-up questions as simple strings.

    This thin wrapper delegates to :func:`question_logic.generate_followup_questions`,
    which returns rich question objects including priority levels and
    suggestions. For backwards compatibility, only the ``question`` text is
    exposed here.

    Args:
        jd: Parsed job description data.
        lang: Language for generated questions.

    Returns:
        List of follow-up question strings.
    """

    items = _generate_followup_questions(jd.model_dump(), lang=lang)
    return [it["question"] for it in items if it.get("question")]
