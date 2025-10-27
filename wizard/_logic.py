"""Business logic helpers for the wizard flow.

This module extracts stateful and validation logic from ``wizard.py`` to
provide a clearer separation between UI layout code and the underlying
operations.  Functions in this module intentionally avoid rendering UI
components and instead focus on data coercion, defaults, and state updates.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Mapping

import streamlit as st

from constants.keys import StateKeys, UIKeys
from state import ensure_state
from core.analysis_tools import get_salary_benchmark, resolve_salary_role
from utils.normalization import country_to_iso2


SALARY_SLIDER_MIN = 0
SALARY_SLIDER_MAX = 500_000
SALARY_SLIDER_STEP = 1_000


_MISSING = object()


def _ensure_profile_mapping() -> Mapping[str, Any]:
    """Return the profile mapping stored in session state."""

    profile = st.session_state.get(StateKeys.PROFILE)
    if not isinstance(profile, Mapping):
        ensure_state()
        profile = st.session_state.get(StateKeys.PROFILE)
    if isinstance(profile, Mapping):
        return profile
    return {}


def get_value(field_path: str, default: Any | None = None) -> Any:
    """Return the value stored under ``field_path`` within the profile."""

    if not field_path:
        raise ValueError("field_path must not be empty")

    current: Any = _ensure_profile_mapping()
    for part in field_path.split("."):
        if part == "":
            return default
        if isinstance(current, Mapping):
            candidate = current.get(part, _MISSING)
        else:
            candidate = _MISSING
        if candidate is _MISSING:
            return default
        current = candidate
    return current


def _coerce_logo_bytes(data: Any) -> bytes | None:
    """Return ``data`` as ``bytes`` when it looks like a logo payload."""

    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    return None


def _set_company_logo(data: bytes | bytearray | None) -> None:
    """Persist logo ``data`` under shared session keys for reuse."""

    logo_bytes = _coerce_logo_bytes(data)
    st.session_state[StateKeys.JOB_AD_LOGO_DATA] = logo_bytes
    st.session_state["company_logo"] = logo_bytes


def _get_company_logo_bytes() -> bytes | None:
    """Return the stored company logo, synchronising legacy keys."""

    shared_logo = _coerce_logo_bytes(st.session_state.get(StateKeys.JOB_AD_LOGO_DATA))
    if shared_logo is not None:
        st.session_state["company_logo"] = shared_logo
        return shared_logo

    legacy_logo = _coerce_logo_bytes(st.session_state.get("company_logo"))
    st.session_state["company_logo"] = legacy_logo
    st.session_state[StateKeys.JOB_AD_LOGO_DATA] = legacy_logo
    return legacy_logo


@dataclass(frozen=True)
class _SalaryRangeDefaults:
    """Container for slider defaults."""

    minimum: int
    maximum: int
    currency: str | None


def _to_int(value: Any) -> int | None:
    """Convert ``value`` to ``int`` when possible."""

    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(round(float(value)))
    cleaned = str(value).strip()
    if not cleaned:
        return None
    normalized = cleaned.replace(".", "").replace(",", ".")
    try:
        return int(round(float(normalized)))
    except ValueError:
        return None


def _clamp_salary_value(value: int | None) -> int:
    """Clamp a salary value to the slider boundaries."""

    if value is None:
        return SALARY_SLIDER_MIN
    return max(SALARY_SLIDER_MIN, min(SALARY_SLIDER_MAX, int(value)))


def _parse_salary_range_text(text: str) -> tuple[int | None, int | None]:
    """Extract numeric salary bounds from ``text``."""

    if not text:
        return None, None
    multiplier = 1_000 if "k" in text.lower() else 1
    numbers: list[float] = []
    for raw in re.findall(r"\d+[\d,\.]*", text):
        normalized = raw.replace(".", "").replace(",", ".")
        try:
            numbers.append(float(normalized))
        except ValueError:
            continue
    if not numbers:
        return None, None
    if len(numbers) == 1:
        value = int(round(numbers[0] * multiplier))
        return value, value
    first = int(round(numbers[0] * multiplier))
    second = int(round(numbers[1] * multiplier))
    return first, second


def _infer_currency_from_range(text: str) -> str | None:
    """Infer a currency identifier from textual salary information."""

    if not text:
        return None
    upper = text.upper()
    if "EUR" in upper or "€" in text:
        return "EUR"
    if "USD" in upper or "$" in text:
        return "USD"
    if "GBP" in upper or "£" in text:
        return "GBP"
    if "CHF" in upper or "CHF" in text:
        return "CHF"
    return None


def _benchmark_salary_range(
    profile: Mapping[str, Any],
) -> tuple[int | None, int | None, str | None]:
    """Return salary bounds derived from static benchmark data."""

    position = profile.get("position", {}) if isinstance(profile, Mapping) else {}
    job_title = str(position.get("job_title") or "").strip()
    if not job_title:
        return None, None, None

    location = profile.get("location", {}) if isinstance(profile, Mapping) else {}
    country_raw = str(location.get("country") or "").strip()
    iso_country = country_to_iso2(country_raw) if country_raw else None
    benchmark_role = resolve_salary_role(job_title) or job_title
    bench_country = iso_country or (country_raw.upper() if country_raw else "US")
    benchmark = get_salary_benchmark(benchmark_role, bench_country)
    raw_range = str(benchmark.get("salary_range") or "")
    salary_min, salary_max = _parse_salary_range_text(raw_range)
    currency = _infer_currency_from_range(raw_range)
    if currency is None and iso_country:
        currency = _DEFAULT_CURRENCY_BY_ISO.get(iso_country)
    return salary_min, salary_max, currency


_DEFAULT_CURRENCY_BY_ISO: dict[str, str] = {
    "DE": "EUR",
    "AT": "EUR",
    "CH": "CHF",
    "US": "USD",
    "GB": "GBP",
}


def _derive_salary_range_defaults(profile: Mapping[str, Any]) -> _SalaryRangeDefaults:
    """Compute slider defaults from profile or benchmark information."""

    compensation = profile.get("compensation", {}) if isinstance(profile, Mapping) else {}
    current_min = _to_int(compensation.get("salary_min"))
    current_max = _to_int(compensation.get("salary_max"))
    current_currency = str(compensation.get("currency") or "").strip() or None

    if current_min is not None or current_max is not None:
        minimum = _clamp_salary_value(current_min or current_max)
        maximum = _clamp_salary_value(current_max or current_min)
        if minimum > maximum:
            minimum, maximum = maximum, minimum
        return _SalaryRangeDefaults(minimum, maximum, current_currency)

    estimate = st.session_state.get(UIKeys.SALARY_ESTIMATE) or {}
    estimate_min = _to_int(estimate.get("salary_min"))
    estimate_max = _to_int(estimate.get("salary_max"))
    estimate_currency = str(estimate.get("currency") or "").strip() or None

    if estimate_min is not None or estimate_max is not None:
        minimum = _clamp_salary_value(estimate_min or estimate_max)
        maximum = _clamp_salary_value(estimate_max or estimate_min)
        if minimum > maximum:
            minimum, maximum = maximum, minimum
        return _SalaryRangeDefaults(minimum, maximum, estimate_currency or current_currency)

    benchmark_min, benchmark_max, benchmark_currency = _benchmark_salary_range(profile)
    if benchmark_min is not None or benchmark_max is not None:
        minimum = _clamp_salary_value(benchmark_min or benchmark_max)
        maximum = _clamp_salary_value(benchmark_max or benchmark_min)
        if minimum > maximum:
            minimum, maximum = maximum, minimum
        currency = benchmark_currency or estimate_currency or current_currency
        return _SalaryRangeDefaults(minimum, maximum, currency)

    fallback_min, fallback_max = 50_000, 70_000
    fallback_currency = estimate_currency or current_currency or "EUR"
    return _SalaryRangeDefaults(fallback_min, fallback_max, fallback_currency)


_BULLET_PREFIX = re.compile(r"^[\-\*•]+\s*")


def unique_normalized(values: Iterable[str] | None) -> list[str]:
    """Return ``values`` without duplicates, normalised for comparison."""

    seen: set[str] = set()
    result: list[str] = []
    if not values:
        return result
    for value in values:
        if value is None:
            continue
        cleaned = str(value).strip()
        if not cleaned:
            continue
        marker = cleaned.casefold()
        if marker in seen:
            continue
        seen.add(marker)
        result.append(cleaned)
    return result


def merge_unique_items(existing: Sequence[str] | None, additions: Iterable[str] | None) -> list[str]:
    """Combine ``existing`` items with ``additions`` removing duplicates."""

    base = list(existing) if existing else []
    if not additions:
        return unique_normalized(base)
    combined = list(base)
    combined.extend(str(item) for item in additions if item is not None)
    return unique_normalized(combined)


def normalize_text_area_list(raw_text: str, *, strip_bullets: bool = True) -> list[str]:
    """Split ``raw_text`` into cleaned list items for multi-line inputs."""

    if not raw_text:
        return []
    items: list[str] = []
    for line in raw_text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if strip_bullets:
            cleaned = _BULLET_PREFIX.sub("", cleaned).strip()
        if cleaned:
            items.append(cleaned)
    return items


__all__ = [
    "get_value",
    "_SalaryRangeDefaults",
    "_benchmark_salary_range",
    "_clamp_salary_value",
    "_coerce_logo_bytes",
    "_derive_salary_range_defaults",
    "_get_company_logo_bytes",
    "_infer_currency_from_range",
    "_parse_salary_range_text",
    "_set_company_logo",
    "_to_int",
    "merge_unique_items",
    "normalize_text_area_list",
    "SALARY_SLIDER_MAX",
    "SALARY_SLIDER_MIN",
    "SALARY_SLIDER_STEP",
    "unique_normalized",
]
