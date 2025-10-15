from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, TypedDict

import streamlit as st
from pydantic import BaseModel, Field

from constants.keys import StateKeys, UIKeys
from core.analysis_tools import get_salary_benchmark, resolve_salary_role
from utils.i18n import tr
from utils.normalization import country_to_iso2, normalize_country

try:
    from openai_utils import call_chat_api, build_extraction_tool
except Exception:  # pragma: no cover - during offline tests without OpenAI
    call_chat_api = None  # type: ignore
    build_extraction_tool = None  # type: ignore


logger = logging.getLogger(__name__)


FUNCTION_NAME = "SalaryExpectationResponse"


class SalaryExpectationResponse(BaseModel):
    """Structured response schema for salary expectation estimates."""

    salary_min: float | None = Field(
        default=None,
        description="Lower bound of the expected annual salary in numeric form.",
    )
    salary_max: float | None = Field(
        default=None,
        description="Upper bound of the expected annual salary in numeric form.",
    )
    currency: str | None = Field(
        default=None,
        description="ISO 4217 currency code (e.g. EUR, USD).",
    )
    explanation: str | None = Field(
        default=None,
        description="Short explanation why this range is appropriate.",
        max_length=400,
    )


@dataclass(slots=True)
class _SalaryInputs:
    job_title: str
    country: str
    primary_city: str | None
    hq_location: str | None
    seniority: str | None
    work_policy: str | None
    employment_type: str | None
    company_size: str | None
    industry: str | None
    current_min: float | None
    current_max: float | None
    current_currency: str | None
    required_hard_skills: list[str]
    required_soft_skills: list[str]
    hard_skills_optional: list[str]
    soft_skills_optional: list[str]
    tools_and_technologies: list[str]
    certificates: list[str]
    languages_required: list[str]
    languages_optional: list[str]
    language_level_english: str | None


class SalaryImpact(TypedDict, total=False):
    """Describe how a factor influenced the final salary estimate."""

    absolute: float
    relative: float | None
    user_value: float
    user_currency: str | None
    note: str


class SalaryFactor(TypedDict, total=False):
    """Single entry for the salary explanation table."""

    key: str
    value: Any
    impact: SalaryImpact | None


SalaryExplanation = list[SalaryFactor | str]


def estimate_salary_expectation() -> None:
    """Calculate and persist the salary expectation for the current profile."""

    profile: Mapping[str, Any] = st.session_state.get(StateKeys.PROFILE, {})
    inputs = _collect_inputs(profile)

    has_country = bool(inputs.country)
    has_geo_hint = has_country or inputs.primary_city or inputs.hq_location

    if not inputs.job_title or not has_geo_hint:
        message = tr(
            "Bitte gib mindestens Jobtitel und entweder Land oder Standort an, um eine Schätzung zu erhalten.",
            "Please provide at least a job title plus either a country or a city/HQ location to generate an estimate.",
        )
        st.session_state[UIKeys.SALARY_ESTIMATE] = None
        st.session_state[UIKeys.SALARY_EXPLANATION] = message
        st.session_state[UIKeys.SALARY_REFRESH] = _now_iso()
        return

    result: dict[str, Any] | None = None
    explanation: SalaryExplanation | str | None = None
    source = "model"

    if call_chat_api and build_extraction_tool and not st.session_state.get(
        "openai_api_key_missing"
    ):
        try:
            result, explanation = _call_salary_model(inputs)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Salary estimation via model failed, falling back: %s", exc)
    if result is None:
        source = "fallback"
        result, explanation = _fallback_salary(inputs)

    if not result:
        st.session_state[UIKeys.SALARY_ESTIMATE] = None
        st.session_state[UIKeys.SALARY_EXPLANATION] = explanation
        st.session_state[UIKeys.SALARY_REFRESH] = _now_iso()
        return

    if not result.get("currency"):
        result["currency"] = inputs.current_currency or _guess_currency(inputs.country)

    st.session_state[UIKeys.SALARY_ESTIMATE] = {**result, "source": source}
    st.session_state[UIKeys.SALARY_EXPLANATION] = explanation
    st.session_state[UIKeys.SALARY_REFRESH] = _now_iso()


def _collect_inputs(profile: Mapping[str, Any]) -> _SalaryInputs:
    position = profile.get("position", {}) if isinstance(profile, Mapping) else {}
    location = profile.get("location", {}) if isinstance(profile, Mapping) else {}
    employment = profile.get("employment", {}) if isinstance(profile, Mapping) else {}
    company = profile.get("company", {}) if isinstance(profile, Mapping) else {}
    compensation = (
        profile.get("compensation", {}) if isinstance(profile, Mapping) else {}
    )
    requirements = (
        profile.get("requirements", {}) if isinstance(profile, Mapping) else {}
    )

    def _as_float(value: Any) -> float | None:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _as_str_list(value: Any) -> list[str]:
        if isinstance(value, (list, tuple, set)):
            result: list[str] = []
            for item in value:
                if item is None:
                    continue
                text = str(item).strip()
                if text:
                    result.append(text)
            return result
        return []

    country_raw = str(location.get("country") or "").strip()
    primary_city = str(location.get("primary_city") or "").strip() or None
    hq_location = str(company.get("hq_location") or "").strip() or None
    inferred_country = country_raw or _derive_country_from_locations(primary_city, hq_location) or ""

    return _SalaryInputs(
        job_title=str(position.get("job_title") or "").strip(),
        country=inferred_country,
        primary_city=primary_city,
        hq_location=hq_location,
        seniority=str(position.get("seniority_level") or "").strip() or None,
        work_policy=str(employment.get("work_policy") or "").strip() or None,
        employment_type=str(employment.get("job_type") or "").strip() or None,
        company_size=str(company.get("size") or "").strip() or None,
        industry=str(company.get("industry") or "").strip() or None,
        current_min=_as_float(compensation.get("salary_min")),
        current_max=_as_float(compensation.get("salary_max")),
        current_currency=str(compensation.get("currency") or "").strip() or None,
        required_hard_skills=_as_str_list(requirements.get("hard_skills_required")),
        required_soft_skills=_as_str_list(requirements.get("soft_skills_required")),
        hard_skills_optional=_as_str_list(requirements.get("hard_skills_optional")),
        soft_skills_optional=_as_str_list(requirements.get("soft_skills_optional")),
        tools_and_technologies=_as_str_list(requirements.get("tools_and_technologies")),
        certificates=_as_str_list(
            requirements.get("certificates") or requirements.get("certifications")
        ),
        languages_required=_as_str_list(requirements.get("languages_required")),
        languages_optional=_as_str_list(requirements.get("languages_optional")),
        language_level_english=(
            str(requirements.get("language_level_english") or "").strip() or None
        ),
    )


_LOCATION_SPLIT_RE = re.compile(r"[\n\-/|;,•·]")


def _derive_country_from_locations(*candidates: str | None) -> str | None:
    for candidate in candidates:
        if not candidate:
            continue
        for token in _iter_location_tokens(candidate):
            country = _country_from_hint(token)
            if country:
                return country
    return None


def _iter_location_tokens(value: str) -> list[str]:
    cleaned = value.strip().strip(",•·|/\n")
    if not cleaned:
        return []

    tokens: list[str] = [cleaned]

    for group in re.findall(r"\(([^)]+)\)", cleaned):
        inner = group.strip()
        if inner:
            tokens.append(inner)

    simplified = cleaned.replace("–", " ").replace("—", " ")
    simplified = simplified.replace("-", " ")

    for part in _LOCATION_SPLIT_RE.split(simplified):
        candidate = part.strip()
        if candidate:
            tokens.append(candidate)

    for part in simplified.split():
        piece = part.strip(" ,•·|/")
        if piece:
            tokens.append(piece)

    # Preserve order while removing duplicates
    seen: set[str] = set()
    unique_tokens: list[str] = []
    for token in tokens:
        key = token.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique_tokens.append(token)
    return unique_tokens


def _country_from_hint(value: str) -> str | None:
    normalized = normalize_country(value)
    if normalized:
        iso_from_normalized = country_to_iso2(normalized)
        if iso_from_normalized:
            return normalized

    iso = country_to_iso2(value)
    if iso:
        normalized_iso = normalize_country(iso)
        if normalized_iso and country_to_iso2(normalized_iso):
            return normalized_iso
        return iso

    ascii_value = _strip_accents(value).casefold()
    mapped = _CITY_TO_COUNTRY.get(ascii_value)
    if mapped:
        return mapped
    return None


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


_CITY_TO_COUNTRY: dict[str, str] = {
    "berlin": "Germany",
    "munich": "Germany",
    "muenchen": "Germany",
    "hamburg": "Germany",
    "frankfurt": "Germany",
    "cologne": "Germany",
    "koeln": "Germany",
    "dusseldorf": "Germany",
    "duesseldorf": "Germany",
    "stuttgart": "Germany",
    "vienna": "Austria",
    "wien": "Austria",
    "salzburg": "Austria",
    "zurich": "Switzerland",
    "zuerich": "Switzerland",
    "geneva": "Switzerland",
    "basel": "Switzerland",
    "london": "United Kingdom",
    "manchester": "United Kingdom",
    "paris": "France",
    "madrid": "Spain",
    "barcelona": "Spain",
    "rome": "Italy",
    "milan": "Italy",
    "new york": "United States",
    "san francisco": "United States",
    "los angeles": "United States",
    "boston": "United States",
    "seattle": "United States",
}


def _call_salary_model(inputs: _SalaryInputs) -> tuple[dict[str, Any] | None, str | None]:
    payload = {
        "job_title": inputs.job_title,
        "country": inputs.country,
        "primary_city": inputs.primary_city,
        "seniority": inputs.seniority,
        "work_policy": inputs.work_policy,
        "employment_type": inputs.employment_type,
        "company_size": inputs.company_size,
        "industry": inputs.industry,
        "current_salary_min": inputs.current_min,
        "current_salary_max": inputs.current_max,
        "current_currency": inputs.current_currency,
        "required_hard_skills": inputs.required_hard_skills,
        "required_soft_skills": inputs.required_soft_skills,
        "hard_skills_optional": inputs.hard_skills_optional,
        "soft_skills_optional": inputs.soft_skills_optional,
        "tools_and_technologies": inputs.tools_and_technologies,
        "certificates": inputs.certificates,
        "languages_required": inputs.languages_required,
        "languages_optional": inputs.languages_optional,
        "language_level_english": inputs.language_level_english,
    }
    system_prompt = (
        "You are a compensation analyst operating with GPT-5 prompting discipline. "
        "Mentally draft a brief plan (do not output it) covering inputs to review, "
        "market adjustments, and validation. Follow the plan step by step and do "
        "not stop until the user's query is completely resolved. Follow these steps: "
        "1) Inspect all structured inputs, 2) benchmark against regional and role "
        "expectations while applying sensible adjustments, 3) validate the final "
        "range before responding. Estimate an annual salary range in the local "
        "currency based on the provided job context. Factor in seniority, work "
        "policy, employment type, team size, industry, city hints, required and "
        "optional skills, tools, certifications, and language expectations. Respond "
        f"by calling the function {FUNCTION_NAME}. Prefer realistic mid-market values "
        "and align with the seniority, work policy, and language level requirements if "
        "given."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]

    schema = SalaryExpectationResponse.model_json_schema()
    tools = build_extraction_tool(FUNCTION_NAME, schema, allow_extra=False)
    result = call_chat_api(
        messages,
        temperature=0.2,
        max_tokens=220,
        tools=tools,
        tool_choice={
            "type": "function",
            "function": {"name": FUNCTION_NAME},
        },
        task="salary_estimate",
    )

    arguments = _extract_tool_arguments(result, FUNCTION_NAME)
    data: dict[str, Any] | None = None
    if arguments:
        try:
            data = json.loads(arguments)
        except json.JSONDecodeError:
            logger.debug("Tool arguments not valid JSON: %s", arguments)
    if data is None and result.content:
        try:
            data = json.loads(result.content)
        except json.JSONDecodeError:
            logger.debug("Model content not valid JSON: %s", result.content)

    if not data:
        return None, None

    parsed = SalaryExpectationResponse.model_validate(data)
    return parsed.model_dump(), parsed.explanation


_FALLBACK_ADJUSTMENT_RULES: dict[str, dict[str, Any]] = {
    "required_hard_skills": {
        "attribute": "required_hard_skills",
        "label_de": "Pflicht-Hard-Skills",
        "label_en": "Required hard skills",
        "per_item": 0.02,
        "max": 0.1,
        "offset": 0,
        "description_de": "+2 % je Muss-Kriterium (max. +10 %)",
        "description_en": "+2% per mandatory requirement (max. +10%)",
    },
    "required_soft_skills": {
        "attribute": "required_soft_skills",
        "label_de": "Pflicht-Soft-Skills",
        "label_en": "Required soft skills",
        "per_item": 0.01,
        "max": 0.05,
        "offset": 0,
        "description_de": "+1 % je Muss-Kriterium (max. +5 %)",
        "description_en": "+1% per mandatory requirement (max. +5%)",
    },
    "hard_skills_optional": {
        "attribute": "hard_skills_optional",
        "label_de": "Optionale Hard-Skills",
        "label_en": "Optional hard skills",
        "per_item": 0.0075,
        "max": 0.03,
        "offset": 0,
        "description_de": "+0,75 % je Nice-to-have (max. +3 %)",
        "description_en": "+0.75% per nice-to-have (max. +3%)",
    },
    "soft_skills_optional": {
        "attribute": "soft_skills_optional",
        "label_de": "Optionale Soft-Skills",
        "label_en": "Optional soft skills",
        "per_item": 0.005,
        "max": 0.02,
        "offset": 0,
        "description_de": "+0,5 % je Nice-to-have (max. +2 %)",
        "description_en": "+0.5% per nice-to-have (max. +2%)",
    },
    "tools_and_technologies": {
        "attribute": "tools_and_technologies",
        "label_de": "Tools & Technologien",
        "label_en": "Tools & technologies",
        "per_item": 0.015,
        "max": 0.075,
        "offset": 0,
        "description_de": "+1,5 % je relevantes Tool (max. +7,5 %)",
        "description_en": "+1.5% per relevant tool (max. +7.5%)",
    },
    "certificates": {
        "attribute": "certificates",
        "label_de": "Zertifikate",
        "label_en": "Certificates",
        "per_item": 0.03,
        "max": 0.12,
        "offset": 0,
        "description_de": "+3 % je Pflichtzertifikat (max. +12 %)",
        "description_en": "+3% per required certificate (max. +12%)",
    },
    "languages_required": {
        "attribute": "languages_required",
        "label_de": "Pflichtsprachen",
        "label_en": "Required languages",
        "per_item": 0.015,
        "max": 0.06,
        "offset": 1,
        "description_de": "+1,5 % je weitere Sprache über die erste hinaus (max. +6 %)",
        "description_en": "+1.5% per additional language beyond the first (max. +6%)",
    },
    "languages_optional": {
        "attribute": "languages_optional",
        "label_de": "Optionale Sprachen",
        "label_en": "Optional languages",
        "per_item": 0.005,
        "max": 0.02,
        "offset": 0,
        "description_de": "+0,5 % je optionale Sprache (max. +2 %)",
        "description_en": "+0.5% per optional language (max. +2%)",
    },
}


_LANGUAGE_LEVEL_ADJUSTMENTS: dict[str, dict[str, Any]] = {
    "native": {
        "percent": 0.05,
        "label_de": "Englischniveau",
        "label_en": "English proficiency",
        "description_de": "Native/Muttersprache: +5 %",
        "description_en": "Native level: +5%",
    },
    "c2": {
        "percent": 0.05,
        "label_de": "Englischniveau",
        "label_en": "English proficiency",
        "description_de": "C2: +5 %",
        "description_en": "C2: +5%",
    },
    "c1": {
        "percent": 0.03,
        "label_de": "Englischniveau",
        "label_en": "English proficiency",
        "description_de": "C1: +3 %",
        "description_en": "C1: +3%",
    },
    "b2": {
        "percent": 0.015,
        "label_de": "Englischniveau",
        "label_en": "English proficiency",
        "description_de": "B2: +1,5 %",
        "description_en": "B2: +1.5%",
    },
    "b1": {
        "percent": 0.005,
        "label_de": "Englischniveau",
        "label_en": "English proficiency",
        "description_de": "B1: +0,5 %",
        "description_en": "B1: +0.5%",
    },
    "a2": {
        "percent": 0.0,
        "label_de": "Englischniveau",
        "label_en": "English proficiency",
        "description_de": "A2 oder niedriger: kein Zuschlag",
        "description_en": "A2 or lower: no adjustment",
    },
}


def _compute_adjustment_percentage(inputs: _SalaryInputs) -> tuple[float, list[str], list[str]]:
    total = 0.0
    applied_de: list[str] = []
    applied_en: list[str] = []

    for rule in _FALLBACK_ADJUSTMENT_RULES.values():
        attr = rule["attribute"]
        value = getattr(inputs, attr)
        raw_count = len(value) if isinstance(value, list) else (1 if value else 0)
        if raw_count <= 0:
            continue
        offset = rule.get("offset", 0)
        effective_count = max(raw_count - offset, 0)
        if effective_count <= 0:
            continue
        per_item = rule["per_item"]
        max_total = rule.get("max")
        pct = effective_count * per_item
        if isinstance(max_total, (int, float)):
            pct = min(pct, max_total)
        total += pct
        applied_de.append(
            f"{rule['label_de']}: {pct:+.1%} ({rule['description_de']})"
        )
        applied_en.append(
            f"{rule['label_en']}: {pct:+.1%} ({rule['description_en']})"
        )

    level = (inputs.language_level_english or "").strip().lower()
    if level:
        matched = None
        for key, data in _LANGUAGE_LEVEL_ADJUSTMENTS.items():
            if level == key or level.startswith(key):
                matched = data
                break
        if matched:
            pct = matched["percent"]
            total += pct
            applied_de.append(
                f"{matched['label_de']}: {pct:+.1%} ({matched['description_de']})"
            )
            applied_en.append(
                f"{matched['label_en']}: {pct:+.1%} ({matched['description_en']})"
            )

    total = max(min(total, 0.25), -0.2)
    return total, applied_de, applied_en


def _apply_adjustment(value: float | None, multiplier: float) -> float | None:
    if value is None:
        return None
    adjusted = value * multiplier
    return round(adjusted, 2)


def _fallback_salary(
    inputs: _SalaryInputs,
) -> tuple[dict[str, Any] | None, SalaryExplanation | str | None]:
    role_key = _canonical_salary_role(inputs.job_title)
    iso_country = country_to_iso2(inputs.country)
    bench_country = iso_country or (
        inputs.country.strip().upper() if inputs.country else None
    )
    benchmark_role = role_key or inputs.job_title
    bench = get_salary_benchmark(benchmark_role, bench_country or "US")
    raw_range = bench.get("salary_range", "")
    salary_min, salary_max = _parse_benchmark_range(raw_range)
    currency = _infer_currency_from_text(raw_range) or _guess_currency(
        iso_country or inputs.country
    )

    if salary_min is None and salary_max is None:
        message = tr(
            "Keine Vergleichsdaten gefunden – bitte trage eigene Werte ein.",
            "No benchmark data available – please enter your own range.",
        )
        return None, message

    adjustment_pct, applied_de, applied_en = _compute_adjustment_percentage(inputs)
    if adjustment_pct:
        multiplier = 1 + adjustment_pct
        salary_min = _apply_adjustment(salary_min, multiplier)
        salary_max = _apply_adjustment(salary_max, multiplier)

    explanation_de = "Fallback auf statische Benchmark-Daten."
    explanation_en = "Used static benchmark data as fallback."
    if applied_de and applied_en:
        explanation_de += " Zuschläge/Abschläge: " + "; ".join(applied_de) + "."
        explanation_en += " Adjustments: " + "; ".join(applied_en) + "."

    structured_explanation = _build_fallback_explanation(
        inputs,
        benchmark_role,
        bench_country,
        currency,
        salary_min,
        salary_max,
        raw_range,
    )

    structured_explanation.insert(
        1,
        {
            "key": "summary",
            "value": tr(explanation_de, explanation_en),
            "impact": None,
        },
    )

    if applied_de or applied_en:
        adjustments_value_de = "; ".join(applied_de) if applied_de else "Keine Anpassungen"
        adjustments_value_en = (
            "; ".join(applied_en) if applied_en else "No adjustments applied"
        )
        structured_explanation.append(
            {
                "key": "adjustments",
                "value": tr(adjustments_value_de, adjustments_value_en),
                "impact": None,
            }
        )
        structured_explanation.extend([entry.split(":")[0] for entry in applied_de])

    return (
        {"salary_min": salary_min, "salary_max": salary_max, "currency": currency},
        structured_explanation,
    )


def _build_fallback_explanation(
    inputs: _SalaryInputs,
    benchmark_role: str | None,
    bench_country: str | None,
    currency: str | None,
    salary_min: float | None,
    salary_max: float | None,
    raw_range: str,
) -> SalaryExplanation:
    explanation: SalaryExplanation = [
        {
            "key": "source",
            "value": tr(
                "Fallback: Benchmark-Daten",
                "Fallback: benchmark data",
            ),
            "impact": {"note": "fallback_source"},
        }
    ]

    if benchmark_role:
        explanation.append(
            {
                "key": "benchmark_role",
                "value": benchmark_role,
                "impact": None,
            }
        )
    if bench_country:
        explanation.append(
            {
                "key": "benchmark_country",
                "value": bench_country,
                "impact": None,
            }
        )
    if raw_range:
        explanation.append(
            {
                "key": "benchmark_range_raw",
                "value": raw_range,
                "impact": None,
            }
        )
    if currency:
        explanation.append(
            {
                "key": "currency",
                "value": currency,
                "impact": None,
            }
        )

    if salary_min is not None:
        explanation.append(
            {
                "key": "salary_min",
                "value": salary_min,
                "impact": _build_salary_impact(
                    inputs.current_min,
                    salary_min,
                    inputs.current_currency,
                    currency,
                ),
            }
        )
    if salary_max is not None:
        explanation.append(
            {
                "key": "salary_max",
                "value": salary_max,
                "impact": _build_salary_impact(
                    inputs.current_max,
                    salary_max,
                    inputs.current_currency,
                    currency,
                ),
            }
        )

    return explanation


def _build_salary_impact(
    user_value: float | None,
    benchmark_value: float | None,
    user_currency: str | None,
    benchmark_currency: str | None,
) -> SalaryImpact | None:
    if benchmark_value is None:
        return {"note": "no_benchmark_value"}
    if user_value is None:
        return {"note": "no_user_input"}

    absolute = user_value - benchmark_value
    relative = None
    if benchmark_value:
        relative = absolute / benchmark_value

    impact: SalaryImpact = {
        "absolute": absolute,
        "relative": relative,
        "user_value": user_value,
        "user_currency": user_currency,
    }

    if (
        user_currency
        and benchmark_currency
        and user_currency.strip().upper() != benchmark_currency.strip().upper()
    ):
        impact["note"] = "currency_mismatch"

    return impact


def _canonical_salary_role(job_title: str) -> str | None:
    """Normalize ``job_title`` and map it to a canonical benchmark role."""

    normalized = unicodedata.normalize("NFKD", job_title or "")
    ascii_title = "".join(char for char in normalized if not unicodedata.combining(char))
    compact = " ".join(ascii_title.lower().split())
    if not compact:
        return None

    canonical = resolve_salary_role(job_title)
    if canonical:
        return canonical

    canonical = resolve_salary_role(compact)
    if canonical:
        return canonical

    return compact


def _extract_tool_arguments(result: Any, name: str) -> str | None:
    for call in result.tool_calls:
        function = call.get("function", {})
        if function.get("name") == name:
            arguments = function.get("arguments")
            if isinstance(arguments, str):
                return arguments
    return None


def _parse_benchmark_range(text: str) -> tuple[float | None, float | None]:
    if not text:
        return None, None
    multiplier = 1.0
    if "k" in text.lower():
        multiplier = 1000.0
    numbers = [float(match.replace(",", ".")) for match in re.findall(r"\d+[\d,\.]*", text)]
    if not numbers:
        return None, None
    if len(numbers) == 1:
        value = numbers[0] * multiplier
        return value, value
    first, second = numbers[0], numbers[1]
    return first * multiplier, second * multiplier


def _infer_currency_from_text(text: str) -> str | None:
    text_upper = text.upper()
    if "USD" in text_upper or "$" in text:
        return "USD"
    if "EUR" in text_upper or "€" in text:
        return "EUR"
    if "GBP" in text_upper or "£" in text:
        return "GBP"
    return None


_CURRENCY_BY_ISO: dict[str, str] = {
    "DE": "EUR",
    "AT": "EUR",
    "CH": "CHF",
    "US": "USD",
    "GB": "GBP",
    "BE": "EUR",
    "FR": "EUR",
    "ES": "EUR",
    "IT": "EUR",
}

_CURRENCY_BY_NAME: dict[str, str] = {
    "GERMANY": "EUR",
    "AUSTRIA": "EUR",
    "SWITZERLAND": "CHF",
    "UNITED STATES": "USD",
    "UNITED KINGDOM": "GBP",
}


def _guess_currency(country: str | None) -> str | None:
    if not country:
        return None

    iso_code = country_to_iso2(country)
    if iso_code:
        currency = _CURRENCY_BY_ISO.get(iso_code)
        if currency:
            return currency

    normalized = normalize_country(country)
    if normalized:
        normalized_upper = normalized.upper()
        currency = _CURRENCY_BY_NAME.get(normalized_upper)
        if currency:
            return currency
        iso_from_name = country_to_iso2(normalized)
        if iso_from_name:
            currency = _CURRENCY_BY_ISO.get(iso_from_name)
            if currency:
                return currency

    upper_country = country.strip().upper()
    return _CURRENCY_BY_ISO.get(upper_country) or _CURRENCY_BY_NAME.get(upper_country)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["estimate_salary_expectation"]
