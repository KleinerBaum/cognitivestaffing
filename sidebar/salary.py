from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

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


FUNCTION_NAME = "update_salary_expectation"


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
    explanation: str | None = None
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
        st.session_state[UIKeys.SALARY_EXPLANATION] = explanation or ""
        st.session_state[UIKeys.SALARY_REFRESH] = _now_iso()
        return

    if not result.get("currency"):
        result["currency"] = inputs.current_currency or _guess_currency(inputs.country)

    st.session_state[UIKeys.SALARY_ESTIMATE] = {**result, "source": source}
    st.session_state[UIKeys.SALARY_EXPLANATION] = explanation or ""
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
    }
    system_prompt = (
        "You are a compensation analyst. Estimate an annual salary range in the "
        "local currency based on the provided job context, considering any city "
        "hints and required skills. Respond by calling the "
        f"function {FUNCTION_NAME}. Prefer realistic mid-market values and align "
        "with the seniority and work policy if given."
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
        tool_choice={"type": "function", "name": FUNCTION_NAME},
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


def _fallback_salary(inputs: _SalaryInputs) -> tuple[dict[str, Any] | None, str | None]:
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

    explanation = tr(
        "Fallback auf statische Benchmark-Daten.",
        "Used static benchmark data as fallback.",
    )
    return (
        {"salary_min": salary_min, "salary_max": salary_max, "currency": currency},
        explanation,
    )


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
