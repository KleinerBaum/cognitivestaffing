from __future__ import annotations

import json
import logging
import math
import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from collections.abc import Iterable
from typing import Any, Callable, Mapping, Sequence, TypedDict, cast

import streamlit as st
from pydantic import BaseModel, ConfigDict, Field
import plotly.graph_objects as go

from config import APIMode, ModelTask, get_model_for
from constants.keys import StateKeys, UIKeys
from core.analysis_tools import get_salary_benchmark, resolve_salary_role
from core.suggestions import get_static_benefit_shortlist
from prompts import prompt_registry
from utils.i18n import tr
from utils.normalization import country_to_iso2, normalize_country

CallChatApi = Callable[..., Any]
BuildExtractionTool = Callable[..., list[dict[str, Any]]]

try:
    from openai_utils import build_extraction_tool as _build_extraction_tool
    from openai_utils import call_chat_api as _call_chat_api
except Exception:  # pragma: no cover - during offline tests without OpenAI
    call_chat_api: CallChatApi | None = None
    build_extraction_tool: BuildExtractionTool | None = None
else:
    call_chat_api = cast(CallChatApi, _call_chat_api)
    build_extraction_tool = cast(BuildExtractionTool, _build_extraction_tool)


logger = logging.getLogger(__name__)


FUNCTION_NAME = "SalaryExpectationResponse"


class SalaryExpectationResponse(BaseModel):
    """Structured response schema for salary expectation estimates."""

    model_config = ConfigDict(extra="forbid")

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
    core_responsibilities: list[str]
    must_have_requirements: list[str]
    nice_to_have_requirements: list[str]
    tools_tech_certificates: list[str]


@dataclass(slots=True)
class SalaryFactorEntry:
    """Normalized entry describing a factor influencing the salary estimate."""

    key: str
    label: str
    value_display: str
    impact_summary: str
    explanation: str
    magnitude: float


@dataclass(slots=True)
class BenefitSuggestionBundle:
    """Resolved benefit suggestions grouped by source."""

    suggestions: list[str]
    llm_suggestions: list[str]
    fallback_suggestions: list[str]
    source: str


_FACTOR_LABELS: dict[str, tuple[str, str]] = {
    "source": ("Quelle", "Source"),
    "benchmark_role": ("Benchmark-Rolle", "Benchmark role"),
    "benchmark_country": ("Benchmark-Land", "Benchmark country"),
    "benchmark_range_raw": ("Rohbereich", "Raw range"),
    "currency": ("Währung", "Currency"),
    "salary_min": ("Unteres Benchmark-Ende", "Benchmark lower bound"),
    "salary_max": ("Oberes Benchmark-Ende", "Benchmark upper bound"),
    "summary": ("Zusammenfassung", "Summary"),
    "adjustments": ("Angewandte Anpassungen", "Applied adjustments"),
    "core_responsibilities": ("Kernaufgaben", "Core responsibilities"),
    "must_have_requirements": ("Muss-Anforderungen", "Must-have requirements"),
    "nice_to_have_requirements": ("Nice-to-have-Kriterien", "Nice-to-have requirements"),
    "tools_tech_certificates": ("Tools, Tech & Zertifikate", "Tools, tech & certificates"),
    "languages_required": ("Pflichtsprachen", "Required languages"),
    "languages_optional": ("Zusätzliche Sprachen", "Optional languages"),
}


_IMPACT_NOTES: dict[str, tuple[str, str]] = {
    "fallback_source": (
        "Automatischer Fallback auf Benchmark-Daten",
        "Automatic fallback to benchmark data",
    ),
    "no_user_input": (
        "Keine Nutzereingabe zum Vergleich",
        "No user input to compare",
    ),
    "no_benchmark_value": (
        "Keine Benchmark-Werte verfügbar",
        "No benchmark values available",
    ),
    "currency_mismatch": (
        "Nutzereingabe in anderer Währung",
        "User input uses different currency",
    ),
}


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


@dataclass(slots=True, frozen=True)
class SalaryRequirementStatus:
    """Represent the availability of a required input for salary estimation."""

    path: str
    label: tuple[str, str]
    value: str | None
    satisfied: bool
    group: str | None = None


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

    if (
        call_chat_api is not None
        and build_extraction_tool is not None
        and not st.session_state.get("openai_api_key_missing")
    ):
        try:
            result, explanation = _call_salary_model(
                inputs,
                call_api=call_chat_api,
                extraction_tool_factory=build_extraction_tool,
            )
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


def build_salary_requirements(profile: Mapping[str, Any]) -> tuple[_SalaryInputs, list[SalaryRequirementStatus], bool]:
    """Return the collected inputs plus requirement status entries."""

    inputs = _collect_inputs(profile)

    job_label = ("Jobtitel", "Job title")
    job_value = inputs.job_title or None
    requirement_entries: list[SalaryRequirementStatus] = [
        SalaryRequirementStatus(
            path="position.job_title",
            label=job_label,
            value=job_value,
            satisfied=bool(job_value),
        )
    ]

    geo_requirements = [
        SalaryRequirementStatus(
            path="location.country",
            label=("Land", "Country"),
            value=inputs.country or None,
            satisfied=bool(inputs.country),
            group="geo",
        ),
        SalaryRequirementStatus(
            path="location.primary_city",
            label=("Hauptstandort", "Primary city"),
            value=inputs.primary_city or None,
            satisfied=bool(inputs.primary_city),
            group="geo",
        ),
        SalaryRequirementStatus(
            path="company.hq_location",
            label=("Unternehmenssitz", "Company HQ"),
            value=inputs.hq_location or None,
            satisfied=bool(inputs.hq_location),
            group="geo",
        ),
    ]

    requirement_entries.extend(geo_requirements)

    geo_ready = any(entry.satisfied for entry in geo_requirements)
    ready = bool(job_value) and geo_ready

    return inputs, requirement_entries, ready


def salary_input_signature(inputs: _SalaryInputs) -> str:
    """Generate a deterministic signature for salary inputs to detect changes."""

    payload = asdict(inputs)
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def prepare_salary_factor_entries(
    explanation: object,
    *,
    benchmark_currency: str | None,
    user_currency: str | None,
) -> list[SalaryFactorEntry]:
    """Normalize explanation data for rendering in the sidebar."""

    factors: list[Mapping[str, Any]] = []
    if isinstance(explanation, list):
        factors = [item for item in explanation if isinstance(item, Mapping)]
    elif isinstance(explanation, Mapping):
        candidate = explanation.get("factors") if "factors" in explanation else None
        if isinstance(candidate, list):
            factors = [item for item in candidate if isinstance(item, Mapping)]
        else:
            for key, value in explanation.items():
                if isinstance(value, Mapping):
                    item = dict(value)
                    item.setdefault("key", key)
                    factors.append(item)
                else:
                    factors.append({"key": key, "value": value, "impact": None})

    entries: list[SalaryFactorEntry] = []
    for factor in factors:
        key = str(factor.get("key", ""))
        label = _factor_label(key)
        value_display = _factor_value(key, factor.get("value"), benchmark_currency)
        impact_mapping = factor.get("impact")
        impact_summary = _factor_impact(
            impact_mapping,
            benchmark_currency,
            user_currency,
        )
        explanation_text = _factor_explanation(
            label,
            value_display,
            impact_mapping,
            benchmark_currency,
            user_currency,
        )
        entries.append(
            SalaryFactorEntry(
                key=key,
                label=label,
                value_display=value_display,
                impact_summary=impact_summary,
                explanation=explanation_text,
                magnitude=_factor_magnitude(impact_mapping),
            )
        )

    return entries


def build_factor_influence_chart(factors: Sequence[SalaryFactorEntry]) -> go.Figure:
    """Create a pie chart describing the most influential salary factors."""

    labels = [_format_factor_option(factor) for factor in factors]
    magnitudes = [abs(factor.magnitude) for factor in factors]
    total = sum(magnitudes)
    if total == 0:
        magnitudes = [1 for _ in factors]
        total = len(factors)
    percentages = [(value / total) * 100 for value in magnitudes]
    colors = _generate_factor_colors(len(factors))

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=percentages,
                hole=0.25,
                textinfo="label+percent",
                hoverinfo="label+percent",
                marker=dict(
                    colors=colors,
                    line=dict(color="rgba(0, 0, 0, 0.3)", width=2),
                ),
                pull=[0.05] * len(labels),
                direction="clockwise",
                sort=False,
            )
        ]
    )

    fig.update_traces(
        textfont=dict(color="#ffffff", size=14),
        insidetextorientation="radial",
    )
    fig.update_layout(
        showlegend=False,
        margin=dict(l=0, r=0, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def format_salary_range(salary_min: Any, salary_max: Any, currency: str | None) -> str:
    """Format a salary range for display."""

    currency = currency or ""
    if salary_min is None and salary_max is None:
        return tr("Keine Angaben", "No data")

    def _fmt(value: Any) -> str:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return str(value)
        formatted = f"{numeric:,.0f}".replace(",", "·")
        return f"{formatted} {currency}".strip() if currency else formatted

    if salary_min is not None and salary_max is not None:
        return f"{_fmt(salary_min)} – {_fmt(salary_max)}"
    value = salary_min if salary_min is not None else salary_max
    return _fmt(value)


def resolve_sidebar_benefits(
    *,
    lang: str,
    industry: str,
) -> BenefitSuggestionBundle:
    """Return benefit suggestions for the sidebar with fallback awareness."""

    state = st.session_state.get(StateKeys.BENEFIT_SUGGESTIONS, {})
    llm_pool = _normalize_suggestion_list(state.get("llm", []))
    fallback_pool = _normalize_suggestion_list(
        state.get("fallback", []) or get_static_benefit_shortlist(lang=lang, industry=industry)
    )

    if llm_pool:
        source = "llm"
        primary = llm_pool
    elif fallback_pool:
        source = "fallback"
        primary = fallback_pool
    else:
        source = "none"
        primary = []

    return BenefitSuggestionBundle(
        suggestions=primary,
        llm_suggestions=llm_pool,
        fallback_suggestions=fallback_pool,
        source=source,
    )


def _normalize_suggestion_list(raw: object) -> list[str]:
    if not raw:
        return []
    items: list[str] = []
    seen: set[str] = set()
    if isinstance(raw, Mapping):
        iterable: Iterable[object] = raw.values()
    elif isinstance(raw, (list, tuple, set)):
        iterable = raw
    else:
        iterable = [raw]
    for entry in iterable:
        text = str(entry or "").strip()
        if not text:
            continue
        marker = text.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        items.append(text)
    return items


def _factor_label(key: str) -> str:
    de, en = _FACTOR_LABELS.get(
        key,
        (key.replace("_", " ").replace(".", " → ").title(),) * 2,
    )
    return tr(de, en)


def _factor_value(key: str, value: Any, currency: str | None) -> str:
    if value is None or value == "":
        return tr("Keine Angaben", "No data")
    if key in {"salary_min", "salary_max"}:
        return _format_salary_value(value, currency)
    if isinstance(value, float):
        return f"{value:,.0f}".replace(",", "·")
    return str(value)


def _impact_note_text(note: Any) -> str | None:
    if not note:
        return None
    lookup = _IMPACT_NOTES.get(str(note))
    if lookup:
        return tr(*lookup)
    return str(note)


def _factor_impact(
    impact: Any,
    benchmark_currency: str | None,
    user_currency: str | None,
) -> str:
    if not impact:
        return tr("Keine Auswirkung berechnet", "No impact calculated")
    if not isinstance(impact, Mapping):
        return str(impact)

    parts: list[str] = []
    note_text = _impact_note_text(impact.get("note"))
    if note_text:
        parts.append(note_text)

    absolute = impact.get("absolute")
    currency_to_use = impact.get("user_currency") or user_currency or benchmark_currency
    if isinstance(absolute, (int, float)) and not math.isnan(absolute):
        parts.append(_format_salary_value(absolute, currency_to_use, signed=True))

    relative = impact.get("relative")
    if isinstance(relative, (int, float)) and math.isfinite(relative):
        parts.append(f"({relative:+.1%})")

    user_value = impact.get("user_value")
    if user_value is not None:
        user_value_text = _format_salary_value(
            user_value,
            impact.get("user_currency") or user_currency or benchmark_currency,
        )
        parts.append(tr("vs. Eingabe {value}", "vs. input {value}").format(value=user_value_text))

    filtered = [segment for segment in parts if segment]
    if not filtered:
        return tr("Keine Auswirkung berechnet", "No impact calculated")
    return " · ".join(filtered)


def _factor_explanation(
    label: str,
    value_display: str,
    impact: Any,
    benchmark_currency: str | None,
    user_currency: str | None,
) -> str:
    base_sentence = tr(
        "Faktor {label} mit Referenzwert {value}",
        "Factor {label} with reference value {value}",
    ).format(label=label, value=value_display)

    if not impact:
        second = tr(
            "Für diesen Faktor liegt keine konkrete Auswirkung vor.",
            "There is no concrete impact available for this factor.",
        )
        return f"{base_sentence} {second}"

    if not isinstance(impact, Mapping):
        return f"{base_sentence} {impact}."

    currency_to_use = impact.get("user_currency") or user_currency or benchmark_currency
    absolute = impact.get("absolute")
    absolute_text: str | None = None
    if isinstance(absolute, (int, float)) and math.isfinite(absolute):
        absolute_text = _format_salary_value(absolute, currency_to_use, signed=True)

    relative = impact.get("relative")
    relative_text: str | None = None
    if isinstance(relative, (int, float)) and math.isfinite(relative):
        relative_text = f"{relative:+.1%}"

    user_value = impact.get("user_value")
    user_value_text: str | None = None
    if user_value is not None:
        user_value_text = _format_salary_value(
            user_value,
            impact.get("user_currency") or user_currency or benchmark_currency,
        )

    detail_parts: list[str] = []
    if absolute_text and relative_text:
        detail_parts.append(
            tr(
                "einer Anpassung von {absolute} (entspricht {relative})",
                "an adjustment of {absolute} (equal to {relative})",
            ).format(absolute=absolute_text, relative=relative_text)
        )
    elif absolute_text:
        detail_parts.append(
            tr(
                "einer Anpassung von {absolute}",
                "an adjustment of {absolute}",
            ).format(absolute=absolute_text)
        )
    elif relative_text:
        detail_parts.append(
            tr(
                "einer Veränderung von {relative}",
                "a change of {relative}",
            ).format(relative=relative_text)
        )

    if user_value_text:
        detail_parts.append(
            tr(
                "verglichen mit deiner Eingabe {value}",
                "compared to your input {value}",
            ).format(value=user_value_text)
        )

    second_sentence = ""
    if detail_parts:
        details = " und ".join(detail_parts)
        second_sentence = tr(
            "Das führt zu {details} in der Schätzung.",
            "This results in {details} for the estimate.",
        ).format(details=details)

    note_text = _impact_note_text(impact.get("note"))
    if note_text:
        reason_text = tr("Grund: {note}.", "Reason: {note}.").format(note=note_text)
        if second_sentence:
            second_sentence = f"{second_sentence} {reason_text}"
        else:
            second_sentence = reason_text

    if not second_sentence:
        second_sentence = tr(
            "Für diesen Faktor liegt keine konkrete Auswirkung vor.",
            "There is no concrete impact available for this factor.",
        )

    if not base_sentence.endswith("."):
        base_sentence = f"{base_sentence}."
    if not second_sentence.endswith("."):
        second_sentence = f"{second_sentence}."

    return f"{base_sentence} {second_sentence}"


def _factor_magnitude(impact: Any) -> float:
    if isinstance(impact, Mapping):
        absolute = impact.get("absolute")
        if isinstance(absolute, (int, float)) and math.isfinite(absolute):
            return abs(float(absolute))
        relative = impact.get("relative")
        if isinstance(relative, (int, float)) and math.isfinite(relative):
            return abs(float(relative))
    return 0.0


def _format_salary_value(value: Any, currency: str | None, *, signed: bool = False) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value)

    fmt = f"{numeric:+,.0f}" if signed else f"{numeric:,.0f}"
    fmt = fmt.replace(",", "·")
    if currency:
        return f"{fmt} {currency}".strip()
    return fmt


def _format_factor_option(entry: SalaryFactorEntry) -> str:
    parts: list[str] = [entry.label]
    if entry.value_display:
        parts.append(entry.value_display)
    option_text = " · ".join(part for part in parts if part)
    if entry.impact_summary:
        option_text = option_text + (" — " if option_text else "") + str(entry.impact_summary)
    return option_text


def _generate_factor_colors(count: int) -> list[str]:
    base_palette = [
        "#3b5bdb",
        "#7950f2",
        "#4dabf7",
        "#15aabf",
        "#12b886",
        "#fab005",
        "#f76707",
        "#e8590c",
    ]
    if count <= len(base_palette):
        return base_palette[:count]
    return [base_palette[index % len(base_palette)] for index in range(count)]


def _collect_inputs(profile: Mapping[str, Any]) -> _SalaryInputs:
    position = profile.get("position", {}) if isinstance(profile, Mapping) else {}
    location = profile.get("location", {}) if isinstance(profile, Mapping) else {}
    employment = profile.get("employment", {}) if isinstance(profile, Mapping) else {}
    company = profile.get("company", {}) if isinstance(profile, Mapping) else {}
    compensation = profile.get("compensation", {}) if isinstance(profile, Mapping) else {}
    requirements = profile.get("requirements", {}) if isinstance(profile, Mapping) else {}
    responsibilities = profile.get("responsibilities", {}) if isinstance(profile, Mapping) else {}

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

    def _merge_unique(*iterables: Iterable[str]) -> list[str]:
        merged: list[str] = []
        seen: set[str] = set()
        for iterable in iterables:
            for item in iterable:
                marker = item.casefold()
                if marker in seen:
                    continue
                seen.add(marker)
                merged.append(item)
        return merged

    country_raw = str(location.get("country") or "").strip()
    primary_city = str(location.get("primary_city") or "").strip() or None
    hq_location = str(company.get("hq_location") or "").strip() or None
    inferred_country = country_raw or _derive_country_from_locations(primary_city, hq_location) or ""

    required_hard = _as_str_list(requirements.get("hard_skills_required"))
    required_soft = _as_str_list(requirements.get("soft_skills_required"))
    optional_hard = _as_str_list(requirements.get("hard_skills_optional"))
    optional_soft = _as_str_list(requirements.get("soft_skills_optional"))
    tools = _as_str_list(requirements.get("tools_and_technologies"))
    certificates = _as_str_list(requirements.get("certificates") or requirements.get("certifications"))
    languages_required = _as_str_list(requirements.get("languages_required"))
    languages_optional = _as_str_list(requirements.get("languages_optional"))
    responsibility_items = _as_str_list(responsibilities.get("items"))

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
        required_hard_skills=required_hard,
        required_soft_skills=required_soft,
        hard_skills_optional=optional_hard,
        soft_skills_optional=optional_soft,
        tools_and_technologies=tools,
        certificates=certificates,
        languages_required=languages_required,
        languages_optional=languages_optional,
        language_level_english=(str(requirements.get("language_level_english") or "").strip() or None),
        core_responsibilities=responsibility_items,
        must_have_requirements=_merge_unique(required_hard, required_soft),
        nice_to_have_requirements=_merge_unique(optional_hard, optional_soft),
        tools_tech_certificates=_merge_unique(tools, certificates),
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


def _call_salary_model(
    inputs: _SalaryInputs,
    *,
    call_api: CallChatApi | None = None,
    extraction_tool_factory: BuildExtractionTool | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    api = call_api or call_chat_api
    tool_factory = extraction_tool_factory or build_extraction_tool
    if api is None or tool_factory is None:
        raise RuntimeError("OpenAI client is unavailable")
    payload = {
        "job_title": inputs.job_title,
        "industry": inputs.industry,
        "country": inputs.country,
        "city": inputs.primary_city or inputs.hq_location,
        "core_responsibilities": inputs.core_responsibilities,
        "must_have_requirements": inputs.must_have_requirements,
        "nice_to_have_requirements": inputs.nice_to_have_requirements,
        "tools_tech_certificates": inputs.tools_tech_certificates,
        "tools_and_technologies": inputs.tools_and_technologies,
        "certificates": inputs.certificates,
        "languages_required": inputs.languages_required,
        "languages_optional": inputs.languages_optional,
        "language_level_english": inputs.language_level_english,
    }
    system_prompt = prompt_registry.format(
        "sidebar.salary.system",
        function_name=FUNCTION_NAME,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]

    schema = SalaryExpectationResponse.model_json_schema()
    tools = tool_factory(FUNCTION_NAME, schema, allow_extra=False)
    model = get_model_for(ModelTask.SALARY_ESTIMATE)
    result = api(
        messages,
        temperature=0.2,
        max_completion_tokens=180,
        tools=tools,
        tool_choice={
            "type": "function",
            "function": {"name": FUNCTION_NAME},
        },
        model=model,
        task=ModelTask.SALARY_ESTIMATE,
        api_mode=APIMode.CLASSIC,
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
    "core_responsibilities": {
        "attribute": "core_responsibilities",
        "label_de": "Kernaufgaben",
        "label_en": "Core responsibilities",
        "per_item": 0.0075,
        "max": 0.045,
        "offset": 0,
        "description_de": "+0,75 % je Kernaufgabe (max. +4,5 %)",
        "description_en": "+0.75% per core responsibility (max. +4.5%)",
    },
    "must_have_requirements": {
        "attribute": "must_have_requirements",
        "label_de": "Muss-Anforderungen",
        "label_en": "Must-have requirements",
        "per_item": 0.015,
        "max": 0.12,
        "offset": 0,
        "description_de": "+1,5 % je Muss-Anforderung (max. +12 %)",
        "description_en": "+1.5% per must-have requirement (max. +12%)",
    },
    "nice_to_have_requirements": {
        "attribute": "nice_to_have_requirements",
        "label_de": "Nice-to-have-Kriterien",
        "label_en": "Nice-to-have requirements",
        "per_item": 0.0075,
        "max": 0.03,
        "offset": 0,
        "description_de": "+0,75 % je Nice-to-have (max. +3 %)",
        "description_en": "+0.75% per nice-to-have (max. +3%)",
    },
    "tools_tech_certificates": {
        "attribute": "tools_tech_certificates",
        "label_de": "Tools, Tech & Zertifikate",
        "label_en": "Tools, tech & certificates",
        "per_item": 0.02,
        "max": 0.12,
        "offset": 0,
        "description_de": "+2 % je Tool/Zertifikat (max. +12 %)",
        "description_en": "+2% per tool or certificate (max. +12%)",
    },
    "languages_required": {
        "attribute": "languages_required",
        "label_de": "Pflichtsprachen",
        "label_en": "Required languages",
        "per_item": 0.015,
        "max": 0.06,
        "offset": 1,
        "description_de": "+1,5 % je weitere Sprache über die erste hinaus (max. +6 %)",
        "description_en": "+1.5% per additional required language beyond the first (max. +6%)",
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
        applied_de.append(f"{rule['label_de']}: {pct:+.1%} ({rule['description_de']})")
        applied_en.append(f"{rule['label_en']}: {pct:+.1%} ({rule['description_en']})")

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
            applied_de.append(f"{matched['label_de']}: {pct:+.1%} ({matched['description_de']})")
            applied_en.append(f"{matched['label_en']}: {pct:+.1%} ({matched['description_en']})")

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
    bench_country = iso_country or (inputs.country.strip().upper() if inputs.country else None)
    benchmark_role = role_key or inputs.job_title
    bench = get_salary_benchmark(benchmark_role, bench_country or "US")
    raw_range = bench.get("salary_range", "")
    salary_min, salary_max = _parse_benchmark_range(raw_range)
    currency = _infer_currency_from_text(raw_range) or _guess_currency(iso_country or inputs.country)

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
        adjustments_value_en = "; ".join(applied_en) if applied_en else "No adjustments applied"
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

    if user_currency and benchmark_currency and user_currency.strip().upper() != benchmark_currency.strip().upper():
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


__all__ = [
    "estimate_salary_expectation",
    "prepare_salary_factor_entries",
    "build_factor_influence_chart",
    "format_salary_range",
    "resolve_sidebar_benefits",
    "SalaryFactorEntry",
    "BenefitSuggestionBundle",
]
