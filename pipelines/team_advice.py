"""Pipeline wrapper for generating team advice in text-only mode."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Sequence

from llm.team_advisor import TeamAdvice, advise_team_structure

logger = logging.getLogger(__name__)


def _fallback_team_advice(lang: str) -> TeamAdvice:
    locale = "de" if lang.lower().startswith("de") else "en"
    if locale == "de":
        message = "Ich konnte gerade keinen Vorschlag generieren. Versuch es bitte erneut."
    else:
        message = "I couldn't generate a suggestion right now. Please try again."
    return TeamAdvice(message=message)


def generate_team_advice(
    profile: Mapping[str, Any],
    *,
    lang: str = "de",
    history: Sequence[Mapping[str, str]] | None = None,
    user_input: str | None = None,
) -> TeamAdvice:
    """Return structured team advice while forcing text-only LLM output."""

    try:
        return advise_team_structure(history, profile, lang=lang, user_input=user_input)
    except Exception as exc:  # pragma: no cover - defensive UI guard
        logger.warning("Team advice pipeline failed; returning fallback message.", exc_info=exc)
        return _fallback_team_advice(lang)


__all__ = ["TeamAdvice", "generate_team_advice"]
