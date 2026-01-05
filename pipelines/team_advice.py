"""Pipeline wrapper for generating team advice in text-only mode."""

from __future__ import annotations

import logging
from typing import Any, Mapping, Sequence

from llm.team_advisor import TeamAdvice, advise_team_structure

logger = logging.getLogger(__name__)


def _fallback_team_advice(lang: str) -> TeamAdvice:
    locale = "de" if lang.lower().startswith("de") else "en"
    if locale == "de":
        message = (
            "Keine KI-Empfehlung verfügbar. Standardtipp: Kläre Berichtslinie und Anzahl direkter"
            " Reports; versuch es später erneut."
        )
    else:
        message = (
            "AI advice is unavailable right now. Default tip: clarify the reporting line and number "
            "of direct reports, then try again later."
        )
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
