from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

import streamlit as st
from pydantic import BaseModel, Field

from constants.keys import StateKeys, UIKeys
from core.analysis_tools import get_salary_benchmark
from utils.i18n import tr

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
    seniority: str | None
    work_policy: str | None
    employment_type: str | None
    company_size: str | None
    industry: str | None
    current_min: float | None
    current_max: float | None
    current_currency: str | None


def estimate_salary_expectation() -> None:
    """Calculate and persist the salary expectation for the current profile."""

    profile: Mapping[str, Any] = st.session_state.get(StateKeys.PROFILE, {})
    inputs = _collect_inputs(profile)

    if not inputs.job_title or not inputs.country:
        message = tr(
            "Bitte gib mindestens Jobtitel und Land an, um eine Schätzung zu erhalten.",
            "Please provide at least job title and country to generate an estimate.",
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

    def _as_float(value: Any) -> float | None:
        try:
            if value is None or value == "":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    return _SalaryInputs(
        job_title=str(position.get("job_title") or "").strip(),
        country=str(location.get("country") or "").strip(),
        seniority=str(position.get("seniority_level") or "").strip() or None,
        work_policy=str(employment.get("work_policy") or "").strip() or None,
        employment_type=str(employment.get("job_type") or "").strip() or None,
        company_size=str(company.get("size") or "").strip() or None,
        industry=str(company.get("industry") or "").strip() or None,
        current_min=_as_float(compensation.get("salary_min")),
        current_max=_as_float(compensation.get("salary_max")),
        current_currency=str(compensation.get("currency") or "").strip() or None,
    )


def _call_salary_model(inputs: _SalaryInputs) -> tuple[dict[str, Any] | None, str | None]:
    payload = {
        "job_title": inputs.job_title,
        "country": inputs.country,
        "seniority": inputs.seniority,
        "work_policy": inputs.work_policy,
        "employment_type": inputs.employment_type,
        "company_size": inputs.company_size,
        "industry": inputs.industry,
        "current_salary_min": inputs.current_min,
        "current_salary_max": inputs.current_max,
        "current_currency": inputs.current_currency,
    }
    system_prompt = (
        "You are a compensation analyst. Estimate an annual salary range in the "
        "local currency based on the provided job context. Respond by calling the "
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
    bench = get_salary_benchmark(inputs.job_title, inputs.country or "US")
    raw_range = bench.get("salary_range", "")
    salary_min, salary_max = _parse_benchmark_range(raw_range)
    currency = _infer_currency_from_text(raw_range) or _guess_currency(inputs.country)

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


def _guess_currency(country: str | None) -> str | None:
    if not country:
        return None
    country = country.upper()
    mapping = {
        "DE": "EUR",
        "AT": "EUR",
        "CH": "CHF",
        "US": "USD",
        "GB": "GBP",
    }
    return mapping.get(country) or ("EUR" if country in {"BE", "FR", "ES", "IT"} else None)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["estimate_salary_expectation"]
