"""Helpers for generating profile suggestions via LLM calls."""

from __future__ import annotations

from typing import Dict, List, Tuple

from openai_utils import suggest_benefits, suggest_skills_for_role

__all__ = ["get_skill_suggestions", "get_benefit_suggestions"]


def get_skill_suggestions(
    job_title: str, lang: str = "en"
) -> Tuple[Dict[str, List[str]], str | None]:
    """Fetch skill suggestions for a role title.

    Args:
        job_title: Target role title.
        lang: Output language ("en" or "de").

    Returns:
        Tuple of (suggestions dict, error message). The suggestions dict contains
        ``tools_and_technologies``, ``hard_skills`` and ``soft_skills`` lists.
        On failure, the dict is empty and ``error`` holds the exception message.
    """

    try:
        return suggest_skills_for_role(job_title, lang=lang), None
    except Exception as err:  # pragma: no cover - error path is tested
        return {}, str(err)


def get_benefit_suggestions(
    job_title: str,
    industry: str = "",
    existing_benefits: str = "",
    lang: str = "en",
) -> Tuple[List[str], str | None]:
    """Fetch benefit suggestions for a role.

    Args:
        job_title: Target role title.
        industry: Optional industry context.
        existing_benefits: Benefits already provided by the user.
        lang: Output language ("en" or "de").

    Returns:
        Tuple of (benefits list, error message). On failure, the list is empty and
        ``error`` contains the exception message.
    """

    try:
        return (
            suggest_benefits(job_title, industry, existing_benefits, lang=lang),
            None,
        )
    except Exception as err:  # pragma: no cover - error path is tested
        return [], str(err)
