"""Helpers for generating profile suggestions via LLM calls."""

from __future__ import annotations

from typing import Dict, List, Tuple

from openai_utils import (
    suggest_benefits,
    suggest_onboarding_plans,
    suggest_skills_for_role,
)

from core.esco_utils import (
    classify_occupation,
    get_essential_skills,
    normalize_skills,
)

__all__ = [
    "get_skill_suggestions",
    "get_benefit_suggestions",
    "get_onboarding_suggestions",
    "get_static_benefit_shortlist",
]


# Default shortlist of benefits used when the AI backend is unavailable or
# returns no suggestions. The lists are intentionally short and localized.
_DEFAULT_BENEFIT_SHORTLIST: Dict[str, Dict[str, List[str]]] = {
    "en": {
        "default": [
            "Flexible working hours",
            "Remote-friendly work",
            "Training budget",
            "Health insurance",
            "Team events",
        ],
        "tech": [
            "Flexible working hours",
            "Remote-first culture",
            "Hardware stipend",
            "Learning & development budget",
            "Stock options",
        ],
        "health": [
            "Subsidized health insurance",
            "Paid wellness days",
            "Retirement plan",
            "Continuous training",
            "Team events",
        ],
    },
    "de": {
        "default": [
            "Flexible Arbeitszeiten",
            "Remote-Option",
            "Weiterbildungsbudget",
            "Gesundheitsleistungen",
            "Team-Events",
        ],
        "tech": [
            "Flexible Arbeitszeiten",
            "Remote-First Kultur",
            "Hardware-Zuschuss",
            "Weiterbildungsbudget",
            "Virtuelle Team-Events",
        ],
        "health": [
            "Bezuschusste Krankenversicherung",
            "Zusätzliche Gesundheitstage",
            "Betriebliche Altersvorsorge",
            "Fortbildungsprogramme",
            "Team-Events",
        ],
    },
}


def _normalize_lang(lang: str) -> str:
    return "de" if str(lang or "").lower().startswith("de") else "en"


def _detect_industry_bucket(industry: str) -> str:
    industry_lc = str(industry or "").lower()
    if any(keyword in industry_lc for keyword in ("health", "care", "medizin", "hospital")):
        return "health"
    if any(
        keyword in industry_lc
        for keyword in (
            "tech",
            "software",
            "it",
            "digital",
            "entwick",
        )
    ):
        return "tech"
    return "default"


def _unique(items: List[str]) -> List[str]:
    seen = set()
    unique_items: List[str] = []
    for raw in items:
        value = str(raw or "").strip()
        if not value:
            continue
        lowered = value.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique_items.append(value)
    return unique_items


def get_static_benefit_shortlist(lang: str = "en", industry: str = "") -> List[str]:
    """Return a localized static benefit shortlist for fallback scenarios."""

    lang_key = _normalize_lang(lang)
    bucket = _detect_industry_bucket(industry)
    items = _DEFAULT_BENEFIT_SHORTLIST.get(lang_key, {}).get(bucket)
    if not items:
        items = _DEFAULT_BENEFIT_SHORTLIST.get("en", {}).get("default", [])
    return _unique(items or [])


def _merge_unique(base: List[str], extra: List[str]) -> List[str]:
    merged = list(base)
    seen = {value.casefold() for value in base}
    for item in extra:
        normalized = str(item or "").strip()
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        merged.append(normalized)
    return merged


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

    suggestions: Dict[str, List[str]] = {
        "tools_and_technologies": [],
        "hard_skills": [],
        "soft_skills": [],
    }
    errors: List[str] = []

    occupation = classify_occupation(job_title, lang=lang)
    if occupation and occupation.get("uri"):
        esco_skills = normalize_skills(
            get_essential_skills(occupation["uri"], lang=lang),
            lang=lang,
        )
        if esco_skills:
            suggestions["hard_skills"] = esco_skills

    try:
        ai_suggestions = suggest_skills_for_role(job_title, lang=lang)
    except Exception as err:  # pragma: no cover - error path is tested
        errors.append(str(err))
    else:
        for key in list(suggestions.keys()):
            values = ai_suggestions.get(key, [])
            if values:
                suggestions[key] = _merge_unique(suggestions[key], values)

    cleaned = {key: value for key, value in suggestions.items() if value}

    return cleaned, "; ".join(errors) if errors else None


def get_benefit_suggestions(
    job_title: str,
    industry: str = "",
    existing_benefits: str = "",
    lang: str = "en",
) -> Tuple[List[str], str | None, bool]:
    """Fetch benefit suggestions for a role.

    Args:
        job_title: Target role title.
        industry: Optional industry context.
        existing_benefits: Benefits already provided by the user.
        lang: Output language ("en" or "de").

    Returns:
        Tuple of (benefits list, error message, used_fallback). On failure or when
        the API returns no suggestions, the fallback list is returned and
        ``used_fallback`` is ``True``. ``error`` contains the exception message
        when the API call failed, otherwise ``None``.
    """

    fallback = get_static_benefit_shortlist(lang=lang, industry=industry)
    try:
        suggestions = _unique(
            suggest_benefits(job_title, industry, existing_benefits, lang=lang)
        )
    except Exception as err:  # pragma: no cover - error path is tested
        return fallback, str(err), True

    if suggestions:
        return suggestions, None, False

    return fallback, None, True


def get_onboarding_suggestions(
    job_title: str,
    *,
    company_name: str = "",
    industry: str = "",
    culture: str = "",
    lang: str = "en",
) -> Tuple[List[str], str | None]:
    """Fetch onboarding process suggestions for the given role context."""

    try:
        suggestions = suggest_onboarding_plans(
            job_title,
            company_name=company_name,
            industry=industry,
            culture=culture,
            lang=lang,
        )
        return suggestions, None
    except Exception as err:  # pragma: no cover - API failure path
        return [], str(err)
