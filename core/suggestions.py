"""Helpers for generating profile suggestions via LLM calls."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Dict, List, Sequence, Tuple

from openai_utils import (
    suggest_onboarding_plans,
    suggest_responsibilities_for_role,
)
from openai_utils import suggest_benefits as legacy_suggest_benefits
from openai_utils import suggest_skills_for_role as legacy_suggest_skills

try:  # Prefer Responses API implementations when available
    from llm.suggestions import (  # type: ignore[attr-defined]
        suggest_benefits as responses_suggest_benefits,
        suggest_skills_for_role as responses_suggest_skills,
    )
except ModuleNotFoundError:  # pragma: no cover - optional dependency during tests
    responses_suggest_benefits = None
    responses_suggest_skills = None

import config as app_config
from utils.llm_state import is_llm_available

_SuggestionFn = Callable[..., Any]


def _select_skill_backend() -> _SuggestionFn:
    if app_config.USE_CLASSIC_API or responses_suggest_skills is None:
        return legacy_suggest_skills
    return responses_suggest_skills


def _select_benefit_backend() -> _SuggestionFn:
    if app_config.USE_CLASSIC_API or responses_suggest_benefits is None:
        return legacy_suggest_benefits
    return responses_suggest_benefits


def suggest_skills_for_role(*args: Any, **kwargs: Any):
    """Proxy skill suggestions to the active backend."""

    backend = _select_skill_backend()
    return backend(*args, **kwargs)


def suggest_benefits(*args: Any, **kwargs: Any):
    """Proxy benefit suggestions to the active backend."""

    backend = _select_benefit_backend()
    return backend(*args, **kwargs)


from core.esco_utils import (
    classify_occupation,
    get_essential_skills,
    lookup_esco_skill,
)

__all__ = [
    "get_skill_suggestions",
    "get_responsibility_suggestions",
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


_TOOL_KEYWORDS = (
    "software",
    "tool",
    "tools",
    "platform",
    "framework",
    "technology",
    "technologies",
    "system",
    "systems",
    "suite",
    "ide",
    "environment",
    "stack",
)

_CERTIFICATE_KEYWORDS = (
    "certific",
    "certified",
    "lizenz",
    "license",
    "licence",
    "abschluss",
    "diploma",
    "degree",
    "zertifikat",
    "accredit",
)


def _fetch_missing_esco_skills_from_state() -> List[str]:
    try:
        import streamlit as st  # type: ignore
        from constants.keys import StateKeys
    except Exception:  # pragma: no cover - optional dependency for non-UI tests
        return []

    try:
        session_state = getattr(st, "session_state", {})
        values = session_state.get(StateKeys.ESCO_MISSING_SKILLS, []) or []
    except Exception:  # pragma: no cover - streamlit guard
        return []

    missing: List[str] = []
    for entry in values:
        if isinstance(entry, str):
            cleaned = entry.strip()
            if cleaned:
                missing.append(cleaned)
    return missing


def _esco_field_and_category(label: str, skill_type: str) -> Tuple[str, str]:
    lowered = label.casefold()
    if any(keyword in lowered for keyword in _CERTIFICATE_KEYWORDS):
        return "certificates", "certificates"
    if any(keyword in lowered for keyword in _TOOL_KEYWORDS):
        return "tools_and_technologies", "tools"

    skill_type_key = skill_type.rsplit("/", 1)[-1].lower() if skill_type else ""
    if skill_type_key == "competence":
        return "soft_skills", "competence"
    if skill_type_key == "knowledge":
        return "hard_skills", "knowledge"
    return "hard_skills", "skill"


def get_skill_suggestions(
    job_title: str,
    lang: str = "en",
    *,
    focus_terms: Sequence[str] | None = None,
    missing_skills: Sequence[str] | None = None,
    tone_style: str | None = None,
    existing_skills: Sequence[str] | None = None,
    responsibilities: Sequence[str] | None = None,
) -> Tuple[Dict[str, Dict[str, List[str]]], str | None]:
    """Fetch skill suggestions for a role title.

    The returned mapping groups values by their origin (e.g. ESCO vs. LLM)
    so that the UI can surface them in grouped multi-select widgets.
    """

    focus_terms = [str(term).strip() for term in (focus_terms or []) if str(term).strip()]
    existing_pool = [
        str(item).strip() for item in (existing_skills or []) if isinstance(item, str) and str(item).strip()
    ]
    responsibility_pool = [
        str(item).strip() for item in (responsibilities or []) if isinstance(item, str) and str(item).strip()
    ]
    existing_markers = {value.casefold() for value in existing_pool}

    grouped: Dict[str, Dict[str, List[str]]] = {
        "tools_and_technologies": {},
        "hard_skills": {},
        "soft_skills": {},
        "certificates": {},
    }
    errors: List[str] = []
    seen: Dict[str, set[str]] = {key: set() for key in grouped}

    def _add_group(field: str, group: str, values: Sequence[str]) -> None:
        cleaned: List[str] = []
        for raw in values:
            value = str(raw or "").strip()
            if not value:
                continue
            marker = value.casefold()
            if marker in seen[field] or marker in existing_markers:
                continue
            seen[field].add(marker)
            cleaned.append(value)
        if cleaned:
            existing = grouped[field].get(group, [])
            grouped[field][group] = existing + cleaned

    occupation = classify_occupation(job_title, lang=lang)
    if occupation and occupation.get("uri"):
        staged: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))

        staged_seen: Dict[str, Dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

        def _stage(field: str, group: str, value: str) -> None:
            marker = value.casefold()
            if marker in staged_seen[field][group]:
                return
            staged_seen[field][group].add(marker)
            staged[field][group].append(value)

        def _process_esco_skill(raw_label: str, *, is_missing: bool) -> None:
            label = str(raw_label or "").strip()
            if not label:
                return
            meta = lookup_esco_skill(label, lang=lang)
            normalized = str(meta.get("preferredLabel") or label).strip()
            if not normalized:
                return
            field, category = _esco_field_and_category(
                normalized,
                str(meta.get("skillType") or ""),
            )
            prefix = "esco_missing" if is_missing else "esco"
            group_name = f"{prefix}_{category}"
            _stage(field, group_name, normalized)

        missing_pool = [
            str(term).strip() for term in (missing_skills or []) if str(term).strip()
        ] or _fetch_missing_esco_skills_from_state()
        for item in missing_pool:
            _process_esco_skill(item, is_missing=True)

        essentials = get_essential_skills(occupation["uri"], lang=lang)
        for item in essentials:
            _process_esco_skill(item, is_missing=False)

        for field, groups in staged.items():
            for group_name, values in groups.items():
                _add_group(field, group_name, values)

    if is_llm_available():
        try:
            ai_suggestions = suggest_skills_for_role(
                job_title,
                lang=lang,
                focus_terms=focus_terms,
                tone_style=tone_style,
                existing_items=existing_pool,
                responsibilities=responsibility_pool,
            )
        except Exception as err:  # pragma: no cover - error path is tested
            errors.append(str(err))
        else:
            for field in grouped:
                values = ai_suggestions.get(field, [])
                if values:
                    _add_group(field, "llm", values)

    cleaned = {key: value for key, value in grouped.items() if value}

    return cleaned, "; ".join(errors) if errors else None


def get_responsibility_suggestions(
    job_title: str,
    *,
    lang: str = "en",
    tone_style: str | None = None,
    company_name: str | None = None,
    team_structure: str | None = None,
    industry: str | None = None,
    existing_items: Sequence[str] | None = None,
    focus_hints: Sequence[str] | None = None,
) -> Tuple[List[str], str | None]:
    """Fetch AI-generated responsibility suggestions for a role."""

    job_title = (job_title or "").strip()
    if not job_title:
        return [], None

    cleaned_existing = [
        str(item).strip() for item in (existing_items or []) if isinstance(item, str) and str(item).strip()
    ]
    existing_markers = {value.casefold() for value in cleaned_existing}

    if not is_llm_available():
        return [], None

    try:
        suggestions = suggest_responsibilities_for_role(
            job_title,
            lang=lang,
            tone_style=tone_style,
            company_name=company_name or "",
            team_structure=team_structure or "",
            industry=industry or "",
            existing_responsibilities=cleaned_existing,
            focus_hints=focus_hints,
        )
    except Exception as exc:  # pragma: no cover - error path tested separately
        return [], str(exc)

    cleaned: List[str] = []
    seen: set[str] = set(existing_markers)
    for raw in suggestions:
        value = str(raw or "").strip()
        if not value:
            continue
        marker = value.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        cleaned.append(value)
    return cleaned, None


def get_benefit_suggestions(
    job_title: str,
    industry: str = "",
    existing_benefits: str = "",
    lang: str = "en",
    *,
    focus_areas: Sequence[str] | None = None,
    tone_style: str | None = None,
) -> Tuple[List[str], str | None, bool]:
    """Fetch benefit suggestions for a role.

    Args:
        job_title: Target role title.
        industry: Optional industry context.
        existing_benefits: Benefits already provided by the user.
        lang: Output language ("en" or "de").
        focus_areas: Optional list of categories the AI should prioritise.

    Returns:
        Tuple of (benefits list, error message, used_fallback). On failure or when
        the API returns no suggestions, the fallback list is returned and
        ``used_fallback`` is ``True``. ``error`` contains the exception message
        when the API call failed, otherwise ``None``.
    """

    fallback = list(get_static_benefit_shortlist(lang=lang, industry=industry))
    if is_llm_available():
        try:
            suggestions = _unique(
                suggest_benefits(
                    job_title,
                    industry,
                    existing_benefits,
                    lang=lang,
                    focus_areas=focus_areas,
                    tone_style=tone_style,
                )
            )
        except Exception as err:  # pragma: no cover - error path is tested
            return list(fallback), str(err), True
    else:
        suggestions = []

    if suggestions:
        return list(suggestions), None, False

    return list(fallback), None, True


def get_onboarding_suggestions(
    job_title: str,
    *,
    company_name: str = "",
    industry: str = "",
    culture: str = "",
    lang: str = "en",
    tone_style: str | None = None,
) -> Tuple[List[str], str | None]:
    """Fetch onboarding process suggestions for the given role context."""

    if not is_llm_available():
        return [], None

    try:
        suggestions = suggest_onboarding_plans(
            job_title,
            company_name=company_name,
            industry=industry,
            culture=culture,
            lang=lang,
            tone_style=tone_style,
        )
        return suggestions, None
    except Exception as err:  # pragma: no cover - API failure path
        return [], str(err)
