"""Responses API helpers for contextual skill and benefit suggestions."""

from __future__ import annotations

import json
import logging
from typing import Any, Sequence

import config as app_config
from config import REASONING_EFFORT
from config.models import ModelTask, get_model_for
from llm.openai_responses import (
    ResponsesCallResult,
    build_json_schema_format,
    call_responses,
)
from llm.response_schemas import (
    BENEFIT_SUGGESTION_SCHEMA_NAME,
    SKILL_SUGGESTION_SCHEMA_NAME,
    get_response_schema,
)
from openai import OpenAIError
from openai_utils.errors import LLMResponseFormatError
from openai_utils.extraction import _format_prompt, _style_prompt_hint
from utils.json_repair import JsonRepairStatus
from utils.skill_suggestions import parse_skill_suggestions_payload

logger = logging.getLogger(__name__)

__all__ = [
    "suggest_skills_for_role",
    "suggest_benefits",
]


def _normalize_lang(lang: str) -> str:
    return "de" if str(lang or "").lower().startswith("de") else "en"


def _clean_string_list(items: Any, *, limit: int | None = None) -> list[str]:
    if not isinstance(items, list):
        return []
    cleaned: list[str] = []
    for entry in items:
        if not isinstance(entry, str):
            continue
        value = entry.strip()
        if not value:
            continue
        cleaned.append(value)
        if limit and len(cleaned) >= limit:
            break
    return cleaned


def _truncate_for_log(value: str | None, *, limit: int = 500) -> str:
    if not value:
        return ""
    snippet = value.strip().replace("\n", " ")
    if len(snippet) > limit:
        return f"{snippet[:limit]}…"
    return snippet


def _fallback_skills_via_legacy(
    job_title: str,
    *,
    lang: str,
    model: str | None,
    focus_terms: Sequence[str] | None,
    tone_style: str | None,
    existing_items: Sequence[str] | None,
    responsibilities: Sequence[str] | None,
) -> dict[str, list[str]]:
    """Return suggestions via the legacy Chat Completions backend."""

    try:
        from openai_utils import suggest_skills_for_role as legacy_suggest_skills

        return legacy_suggest_skills(
            job_title,
            lang=lang,
            model=model,
            focus_terms=focus_terms,
            tone_style=tone_style,
            existing_items=existing_items,
            responsibilities=responsibilities,
        )
    except Exception:  # pragma: no cover - legacy backend should rarely fail
        logger.exception("Legacy skill suggestion fallback failed")
        return {
            "tools_and_technologies": [],
            "hard_skills": [],
            "soft_skills": [],
            "certificates": [],
        }


def _fallback_benefits_static(
    *,
    lang: str,
    industry: str,
    existing_benefits: str,
    focus_areas: Sequence[str] | None,
) -> list[str]:
    """Return a deterministic shortlist of benefits for failure scenarios."""

    focus_seq = [str(area).strip() for area in (focus_areas or []) if str(area).strip()]
    existing_set = {line.strip().lower() for line in str(existing_benefits or "").splitlines() if line.strip()}

    shortlist: list[str] = []
    try:
        from core.suggestions import get_static_benefit_shortlist

        shortlist = list(get_static_benefit_shortlist(lang=lang, industry=industry))
    except Exception:  # pragma: no cover - defensive guard against circular import issues
        logger.exception("Static benefit shortlist fallback failed")

    filtered: list[str] = []
    seen: set[str] = set()
    for benefit in shortlist:
        marker = benefit.strip().lower()
        if not marker or marker in existing_set or marker in seen:
            continue
        seen.add(marker)
        filtered.append(benefit.strip())
        if len(filtered) >= 5:
            break

    for focus in focus_seq:
        marker = focus.lower()
        if marker in existing_set or marker in seen:
            continue
        seen.add(marker)
        filtered.append(focus)
        if len(filtered) >= 5:
            break

    return filtered


def _fallback_benefits_via_legacy(
    job_title: str,
    *,
    industry: str,
    existing_benefits: str,
    lang: str,
    model: str | None,
    focus_areas: Sequence[str] | None,
    tone_style: str | None,
) -> list[str]:
    """Return benefit suggestions using the legacy Chat Completions backend."""

    try:
        from openai_utils import suggest_benefits as legacy_suggest_benefits

        return legacy_suggest_benefits(
            job_title,
            industry=industry,
            existing_benefits=existing_benefits,
            lang=lang,
            model=model,
            focus_areas=focus_areas,
            tone_style=tone_style,
        )
    except Exception:  # pragma: no cover - legacy backend should rarely fail
        logger.exception("Legacy benefit suggestion fallback failed")
        return _fallback_benefits_static(
            lang=lang,
            industry=industry,
            existing_benefits=existing_benefits,
            focus_areas=focus_areas,
        )


def suggest_skills_for_role(
    job_title: str,
    *,
    lang: str = "en",
    model: str | None = None,
    focus_terms: Sequence[str] | None = None,
    tone_style: str | None = None,
    existing_items: Sequence[str] | None = None,
    responsibilities: Sequence[str] | None = None,
) -> dict[str, list[str]]:
    """Return grouped skill suggestions for ``job_title`` via the Responses API."""

    job_title = str(job_title or "").strip()
    if not job_title:
        return {
            "tools_and_technologies": [],
            "hard_skills": [],
            "soft_skills": [],
            "certificates": [],
        }

    if model is None:
        model = get_model_for(ModelTask.SKILL_SUGGESTION)

    locale = _normalize_lang(lang)
    focus_terms = [str(term).strip() for term in (focus_terms or []) if str(term).strip()]
    existing_pool = [
        str(item).strip() for item in (existing_items or []) if isinstance(item, str) and str(item).strip()
    ]
    responsibility_pool = [
        str(item).strip() for item in (responsibilities or []) if isinstance(item, str) and str(item).strip()
    ]

    focus_clause = (
        _format_prompt(
            "llm.extraction.skill_suggestions.focus_clause",
            locale=locale,
            focus_terms=", ".join(focus_terms),
        )
        if focus_terms
        else ""
    )
    existing_clause = (
        _format_prompt(
            "llm.extraction.skill_suggestions.existing_clause",
            locale=locale,
            existing_items="; ".join(existing_pool[:30]),
        )
        if existing_pool
        else ""
    )
    responsibility_clause = (
        _format_prompt(
            "llm.extraction.skill_suggestions.responsibility_clause",
            locale=locale,
            responsibilities="; ".join(responsibility_pool[:12]),
        )
        if responsibility_pool
        else ""
    )

    prompt = _format_prompt(
        "llm.extraction.skill_suggestions.user",
        locale=locale,
        job_title=job_title,
        focus_clause=focus_clause,
        existing_clause=existing_clause,
        responsibility_clause=responsibility_clause,
    )
    tone_hint = _style_prompt_hint(tone_style, locale)
    if tone_hint:
        prompt += f"\n{tone_hint}"

    if app_config.USE_CLASSIC_API:
        logger.info("Using legacy chat API for skill suggestions due to USE_CLASSIC_API flag")
        return _fallback_skills_via_legacy(
            job_title,
            lang=lang,
            model=model,
            focus_terms=focus_terms,
            tone_style=tone_style,
            existing_items=existing_items,
            responsibilities=responsibilities,
        )

    response: ResponsesCallResult | None
    response_format = build_json_schema_format(
        name=SKILL_SUGGESTION_SCHEMA_NAME,
        schema=get_response_schema(SKILL_SUGGESTION_SCHEMA_NAME),
    )
    try:
        response = call_responses(
            [{"role": "user", "content": prompt}],
            model=model,
            response_format=response_format,
            temperature=0.0,
            max_completion_tokens=400,
            reasoning_effort=REASONING_EFFORT,
            task=ModelTask.SKILL_SUGGESTION,
        )
    except LLMResponseFormatError as exc:
        logger.warning(
            "Structured skill suggestion response could not be parsed: %s",
            exc,
        )
        raw_content = exc.raw_content or ""
        logger.debug(
            "Skill suggestion raw output (truncated): %s",
            _truncate_for_log(raw_content),
        )
        response = ResponsesCallResult(
            content=raw_content,
            usage={},
            response_id=None,
            raw_response=None,
            used_chat_fallback=False,
        )
    except OpenAIError as exc:
        logger.warning(
            "Structured skill suggestion call failed; falling back to legacy backend: %s",
            exc,
        )
        response = None

    if response is None:
        logger.warning("Falling back to legacy skill suggestion backend after Responses API failure")
        return _fallback_skills_via_legacy(
            job_title,
            lang=lang,
            model=model,
            focus_terms=focus_terms,
            tone_style=tone_style,
            existing_items=existing_items,
            responsibilities=responsibilities,
        )
    if response.used_chat_fallback:
        logger.info("Skill suggestions succeeded via classic chat fallback")

    try:
        parsed = parse_skill_suggestions_payload(
            response.content or "",
            schema_name=SKILL_SUGGESTION_SCHEMA_NAME,
            schema=get_response_schema(SKILL_SUGGESTION_SCHEMA_NAME),
        )
    except ValueError as exc:
        logger.warning(
            "Responses API skill suggestion failed schema validation; falling back to legacy backend: %s",
            exc,
        )
        logger.debug(
            "Skill suggestion raw output (truncated): %s",
            _truncate_for_log(response.content),
        )
        return _fallback_skills_via_legacy(
            job_title,
            lang=lang,
            model=model,
            focus_terms=focus_terms,
            tone_style=tone_style,
            existing_items=existing_items,
            responsibilities=responsibilities,
        )
    if parsed.payload is None:
        logger.warning(
            "Responses API skill suggestion returned invalid JSON; falling back to legacy backend.",
        )
        logger.debug(
            "Skill suggestion raw output (truncated): %s",
            _truncate_for_log(response.content),
        )
        return _fallback_skills_via_legacy(
            job_title,
            lang=lang,
            model=model,
            focus_terms=focus_terms,
            tone_style=tone_style,
            existing_items=existing_items,
            responsibilities=responsibilities,
        )
    if parsed.status is JsonRepairStatus.REPAIRED:
        logger.info("Skill suggestion JSON required repair before parsing.")

    payload = parsed.payload

    tools = _clean_string_list(payload.get("tools_and_technologies"), limit=12)
    hard = _clean_string_list(payload.get("hard_skills"), limit=12)
    soft = _clean_string_list(payload.get("soft_skills"), limit=12)
    certificates = _clean_string_list(payload.get("certificates"), limit=12)

    try:  # Normalize labels with ESCO helpers when available
        from core.esco_utils import normalize_skills

        tools = normalize_skills(tools, lang=lang)
        hard = normalize_skills(hard, lang=lang)
        soft = normalize_skills(soft, lang=lang)
        certificates = normalize_skills(certificates, lang=lang)
    except Exception:  # pragma: no cover - optional dependency
        pass

    def _unique(seq: list[str], limit: int = 10) -> list[str]:
        seen: set[str] = set()
        unique_items: list[str] = []
        for item in seq:
            marker = item.casefold()
            if marker in seen:
                continue
            seen.add(marker)
            unique_items.append(item)
            if len(unique_items) >= limit:
                break
        return unique_items

    return {
        "tools_and_technologies": _unique(tools),
        "hard_skills": _unique(hard),
        "soft_skills": _unique(soft),
        "certificates": _unique(certificates),
    }


def suggest_benefits(
    job_title: str,
    industry: str = "",
    existing_benefits: str = "",
    lang: str = "en",
    model: str | None = None,
    *,
    focus_areas: Sequence[str] | None = None,
    tone_style: str | None = None,
) -> list[str]:
    """Return benefit suggestions tailored to the provided context."""

    job_title = str(job_title or "").strip()
    if not job_title:
        return []

    if model is None:
        model = get_model_for(ModelTask.BENEFIT_SUGGESTION)

    locale = _normalize_lang(lang)
    focus_areas = [str(area).strip() for area in (focus_areas or []) if str(area).strip()]

    industry_clause = (
        _format_prompt(
            "llm.extraction.benefits.industry_clause",
            locale=locale,
            industry=industry,
        )
        if industry
        else ""
    )
    existing_clause = (
        _format_prompt(
            "llm.extraction.benefits.existing_clause",
            locale=locale,
            existing_benefits=existing_benefits,
        )
        if existing_benefits
        else ""
    )
    focus_clause = (
        _format_prompt(
            "llm.extraction.benefits.focus_clause",
            locale=locale,
            focus_areas=", ".join(focus_areas),
        )
        if focus_areas
        else ""
    )

    prompt = _format_prompt(
        "llm.extraction.benefits.user",
        locale=locale,
        job_title=job_title,
        industry_clause=industry_clause,
        existing_clause=existing_clause,
        focus_clause=focus_clause,
    )
    tone_hint = _style_prompt_hint(tone_style, locale)
    if tone_hint:
        prompt += f"\n{tone_hint}"

    if app_config.USE_CLASSIC_API:
        logger.info("Using legacy chat API for benefit suggestions due to USE_CLASSIC_API flag")
        return _fallback_benefits_via_legacy(
            job_title,
            industry=industry,
            existing_benefits=existing_benefits,
            lang=lang,
            model=model,
            focus_areas=focus_areas,
            tone_style=tone_style,
        )

    def _run_fallback_cascade() -> list[str]:
        static = _fallback_benefits_static(
            lang=lang,
            industry=industry,
            existing_benefits=existing_benefits,
            focus_areas=focus_areas,
        )
        if static:
            return static
        if not app_config.ALLOW_LEGACY_FALLBACKS:
            logger.info("Legacy benefit fallback disabled; returning empty shortlist.")
            return static
        legacy = _fallback_benefits_via_legacy(
            job_title,
            industry=industry,
            existing_benefits=existing_benefits,
            lang=lang,
            model=model,
            focus_areas=focus_areas,
            tone_style=tone_style,
        )
        if legacy:
            return legacy
        return static

    response = call_responses_safe(
        [{"role": "user", "content": prompt}],
        model=model,
        response_format=build_json_schema_format(
            name=BENEFIT_SUGGESTION_SCHEMA_NAME,
            schema=get_response_schema(BENEFIT_SUGGESTION_SCHEMA_NAME),
        ),
        temperature=0.5,
        max_completion_tokens=200,
        reasoning_effort=REASONING_EFFORT,
        task=ModelTask.BENEFIT_SUGGESTION,
        logger_instance=logger,
        context="benefit suggestion",
    )
    if response is None:
        logger.warning(
            "Responses API benefit suggestion failed; using static shortlist before legacy fallback.",
        )
        return _run_fallback_cascade()
    if isinstance(response, ResponsesCallResult) and response.used_chat_fallback:
        logger.info("Benefit suggestions succeeded via classic chat fallback")

    try:
        payload = json.loads(response.content or "{}")
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive parsing
        logger.warning(
            "Responses API benefit suggestion returned invalid JSON; using static shortlist before legacy fallback.",
            exc_info=exc,
        )
        return _run_fallback_cascade()

    def _extract_items(data: Any) -> list[str]:
        if isinstance(data, list):
            return _clean_string_list(data, limit=5)
        if isinstance(data, dict):
            for key in ("items", "benefits", "values"):
                if key in data:
                    nested = _extract_items(data.get(key))
                    if nested:
                        return nested
        return []

    benefits = _extract_items(payload)
    if not benefits and isinstance(response.content, str):
        for line in response.content.splitlines():
            perk = line.strip("-•* \t")
            if perk:
                benefits.append(perk)

    existing_set = {line.strip().lower() for line in existing_benefits.splitlines() if line.strip()}
    filtered: list[str] = []
    seen: set[str] = set()
    for benefit in benefits:
        marker = benefit.strip().lower()
        if not marker or marker in existing_set or marker in seen:
            continue
        seen.add(marker)
        filtered.append(benefit.strip())

    if filtered:
        return filtered

    logger.warning(
        "Responses API produced no benefit items after filtering; using static shortlist before legacy fallback.",
    )
    return _run_fallback_cascade()
