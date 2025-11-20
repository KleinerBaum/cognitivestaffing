"""Business logic helpers for the wizard flow.

This module extracts stateful and validation logic from ``wizard.py`` to
provide a clearer separation between UI layout code and the underlying
operations.  Functions in this module intentionally avoid rendering UI
components and instead focus on data coercion, defaults, and state updates.
"""

from __future__ import annotations

import io
import logging
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Mapping

from pydantic import ValidationError
import streamlit as st
from streamlit.errors import StreamlitAPIException
from utils.i18n import tr

from constants.keys import ProfilePaths, StateKeys, UIKeys
from core.analysis_tools import get_salary_benchmark, resolve_salary_role
from core.normalization import sanitize_optional_url_value
from models.need_analysis import NeedAnalysisProfile
from state import ensure_state
from utils.normalization import (
    country_to_iso2,
    normalize_company_size,
    normalize_country,
    normalize_language_list,
    normalize_phone_number,
    normalize_website_url,
)


if TYPE_CHECKING:  # pragma: no cover - typing-only import path
    from streamlit.runtime.scriptrunner import (
        RerunException as StreamlitRerunException,
        StopException as StreamlitStopException,
    )
else:  # pragma: no cover - Streamlit runtime is unavailable during unit tests
    try:
        from streamlit.runtime.scriptrunner import (
            RerunException as StreamlitRerunException,
            StopException as StreamlitStopException,
        )
    except Exception:

        class StreamlitRerunException(RuntimeError):
            """Fallback rerun exception when Streamlit internals cannot be imported."""

        class StreamlitStopException(RuntimeError):
            """Fallback stop exception when Streamlit internals cannot be imported."""


RerunException = StreamlitRerunException
StopException = StreamlitStopException


SALARY_SLIDER_MIN = 0
SALARY_SLIDER_MAX = 500_000
SALARY_SLIDER_STEP = 1_000


_MISSING = object()


_FIELD_LOCK_BASE_KEY = "ui.locked_field_unlock"


logger = logging.getLogger(__name__)

_RECOVERABLE_WIZARD_ERRORS: tuple[type[Exception], ...] = (
    StreamlitAPIException,
    ValidationError,
    ValueError,
)


def set_in(data: dict, path: str, value: Any) -> None:
    """Assign ``value`` in ``data`` following a dot-separated ``path``."""

    cursor = data
    parts = path.split(".")
    for part in parts[:-1]:
        next_cursor = cursor.get(part)
        if not isinstance(next_cursor, dict):
            next_cursor = {}
            cursor[part] = next_cursor
        cursor = next_cursor
    cursor[parts[-1]] = value


def get_in(data: Mapping[str, Any] | None, path: str, default: Any = None) -> Any:
    """Return the nested value for ``path`` from ``data`` when available."""

    cursor: Any = data
    for part in path.split("."):
        if isinstance(cursor, Mapping) and part in cursor:
            cursor = cursor[part]
        else:
            return default
    return cursor


def _get_profile_state() -> dict[str, Any]:
    """Return the mutable profile mapping from session state."""

    profile = st.session_state.get(StateKeys.PROFILE)
    if isinstance(profile, dict):
        return profile
    ensure_state()
    profile = st.session_state.get(StateKeys.PROFILE)
    if isinstance(profile, dict):
        return profile
    if isinstance(profile, Mapping):
        coerced = dict(profile)
        st.session_state[StateKeys.PROFILE] = coerced
        return coerced
    fallback = NeedAnalysisProfile().model_dump()
    st.session_state[StateKeys.PROFILE] = fallback
    return fallback


def _clear_generated() -> None:
    """Remove cached generated outputs from ``st.session_state``."""

    for key in (
        StateKeys.JOB_AD_MD,
        StateKeys.BOOLEAN_STR,
        StateKeys.INTERVIEW_GUIDE_MD,
        StateKeys.INTERVIEW_GUIDE_DATA,
    ):
        st.session_state.pop(key, None)
    for key in (
        UIKeys.JOB_AD_OUTPUT,
        UIKeys.INTERVIEW_OUTPUT,
    ):
        st.session_state.pop(key, None)


def _normalize_semantic_empty(value: Any) -> Any:
    """Return ``None`` for semantically empty ``value`` entries."""

    if value is None:
        return None
    if isinstance(value, str):
        return value if value.strip() else None
    if isinstance(value, (list, tuple, set, frozenset)):
        return None if len(value) == 0 else value
    if isinstance(value, dict):
        return None if len(value) == 0 else value
    return value


def _normalize_value_for_path(path: str, value: Any) -> Any:
    """Apply field-specific normalisation before persisting ``value``."""

    if path == "company.size":
        if value is None:
            return ""
        candidate = value if isinstance(value, str) else str(value)
        normalized = normalize_company_size(candidate)
        if normalized:
            return normalized
        return " ".join(candidate.strip().split())
    if path == "company.logo_url":
        return sanitize_optional_url_value(value)
    if path == "company.contact_phone":
        if value is None:
            return None
        if isinstance(value, str):
            return normalize_phone_number(value)
        return normalize_phone_number(str(value))
    if path == "company.website":
        if value is None:
            return None
        if isinstance(value, str):
            return normalize_website_url(value)
        return normalize_website_url(str(value))
    if path == "location.country":
        if isinstance(value, str) or value is None:
            return normalize_country(value)
        return normalize_country(str(value))
    if path in {
        "requirements.languages_required",
        "requirements.languages_optional",
    }:
        if isinstance(value, list):
            return normalize_language_list(value)
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",") if part.strip()]
            return normalize_language_list(parts)
        return normalize_language_list([])
    return value


def _clear_field_unlock_state(path: str) -> None:
    """Remove stored unlock toggles for ``path`` across contexts."""

    normalized = path.replace(".", "_")
    prefix = f"{_FIELD_LOCK_BASE_KEY}."
    keys_to_remove = [
        key
        for key in list(st.session_state.keys())
        if isinstance(key, str) and key.startswith(prefix) and key.split(".")[-1] == normalized
    ]
    for key in keys_to_remove:
        st.session_state.pop(key, None)


def _remove_field_lock_metadata(path: str) -> None:
    """Drop lock/high-confidence metadata for ``path`` once the value changes."""

    raw_metadata = st.session_state.get(StateKeys.PROFILE_METADATA, {}) or {}
    if not isinstance(raw_metadata, Mapping):  # pragma: no cover - defensive guard
        return
    metadata = dict(raw_metadata)
    changed = False
    for key in ("locked_fields", "high_confidence_fields"):
        values = metadata.get(key)
        if isinstance(values, list) and path in values:
            metadata[key] = [item for item in values if item != path]
            changed = True
    confidence_map = metadata.get("field_confidence")
    if isinstance(confidence_map, Mapping) and path in confidence_map:
        updated = dict(confidence_map)
        if updated.pop(path, None) is not None:
            metadata["field_confidence"] = updated
            changed = True
    if changed:
        st.session_state[StateKeys.PROFILE_METADATA] = metadata
        _clear_field_unlock_state(path)


def _render_localized_error(message_de: str, message_en: str, error: Exception | None = None) -> None:
    """Display a bilingual error banner with optional expandable details."""

    lang = st.session_state.get("lang", "de")
    st.error(tr(message_de, message_en, lang=lang))
    if error is None:
        return
    label = tr("Fehlerdetails anzeigen", "Show error details", lang=lang)
    try:
        expander = st.expander(label)
    except Exception:  # pragma: no cover - Streamlit shim fallback
        expander = None
    if expander is None:
        if hasattr(st, "write"):
            st.write(repr(error))
        return
    with expander:
        if hasattr(st, "exception"):
            st.exception(error)
        else:  # pragma: no cover - fallback for lightweight Streamlit shims
            st.write(repr(error))


def _handle_profile_update_error(path: str, error: Exception) -> None:
    """Surface a recoverable error raised while updating ``path``."""

    logger.warning("Failed to update profile path '%s': %s", path, error, exc_info=error)
    _render_localized_error(
        (
            f"Automatische Verarbeitung für das Feld „{path}“ ist fehlgeschlagen. "
            "Bitte prüfe die Eingabe oder trage sie manuell ein – die Sitzung bleibt aktiv."
        ),
        (
            f"Automatic processing for the field “{path}” failed. "
            "Please review the value or capture it manually – your session stays active."
        ),
        error,
    )


def _ensure_profile_meta(profile: dict[str, Any]) -> dict[str, Any]:
    """Return the ``meta`` dict for ``profile``, creating it when missing."""

    meta = profile.get("meta")
    if isinstance(meta, dict):
        return meta
    meta = {}
    profile["meta"] = meta
    return meta


def _ensure_followups_answered(profile: dict[str, Any]) -> list[str]:
    """Return the mutable follow-up completion list for ``profile``."""

    meta = _ensure_profile_meta(profile)
    answered = meta.get("followups_answered")
    if isinstance(answered, list):
        cleaned = [item for item in answered if isinstance(item, str)]
        if cleaned is not answered:
            meta["followups_answered"] = cleaned
            return cleaned
        return answered
    meta["followups_answered"] = []
    return meta["followups_answered"]


def _sync_followup_completion(path: str, value: Any, profile: dict[str, Any]) -> None:
    """Synchronise follow-up bookkeeping for ``path`` based on ``value``."""

    answered = _ensure_followups_answered(profile)
    normalized = _normalize_semantic_empty(value)
    if normalized is None:
        if path in answered:
            profile_meta = _ensure_profile_meta(profile)
            profile_meta["followups_answered"] = [item for item in answered if item != path]
        return

    followups = st.session_state.get(StateKeys.FOLLOWUPS)
    if isinstance(followups, list):
        remaining = [q for q in followups if not (isinstance(q, Mapping) and q.get("field") == path)]
        st.session_state[StateKeys.FOLLOWUPS] = remaining
    st.session_state.pop(f"fu_{path}", None)
    if path not in answered:
        answered.append(path)


def _normalize_autofill_value(value: str | None) -> str:
    """Normalize ``value`` for comparison in autofill tracking."""

    if not value:
        return ""
    normalized = " ".join(value.strip().split()).casefold()
    return normalized


def _load_autofill_decisions() -> dict[str, list[str]]:
    """Return a copy of stored autofill rejection decisions."""

    raw = st.session_state.get(StateKeys.WIZARD_AUTOFILL_DECISIONS)
    if not isinstance(raw, Mapping):
        return {}
    decisions: dict[str, list[str]] = {}
    for key, value in raw.items():
        if not isinstance(key, str):
            continue
        if isinstance(value, list):
            items = [str(item) for item in value if isinstance(item, str)]
            decisions[key] = items
    return decisions


def _store_autofill_decisions(decisions: Mapping[str, list[str]]) -> None:
    """Persist ``decisions`` to session state."""

    st.session_state[StateKeys.WIZARD_AUTOFILL_DECISIONS] = {key: list(value) for key, value in decisions.items()}


def _autofill_was_rejected(field_path: str, suggestion: str) -> bool:
    """Return ``True`` when ``suggestion`` was rejected for ``field_path``."""

    normalized = _normalize_autofill_value(suggestion)
    if not normalized:
        return False
    decisions = _load_autofill_decisions()
    rejected = decisions.get(field_path, [])
    return normalized in rejected


def _record_autofill_rejection(field_path: str, suggestion: str) -> None:
    """Remember that ``suggestion`` was rejected for ``field_path``."""

    normalized = _normalize_autofill_value(suggestion)
    if not normalized:
        return
    decisions = _load_autofill_decisions()
    current = set(decisions.get(field_path, []))
    if normalized in current:
        return
    current.add(normalized)
    decisions[field_path] = sorted(current)
    _store_autofill_decisions(decisions)


def _update_profile(
    path: str,
    value: Any,
    *,
    session_value: Any = _MISSING,
    sync_widget_state: bool = True,
) -> None:
    """Update profile data and clear derived outputs if changed.

    Streamlit replays widget defaults on the first rerun after widget
    instantiation, overwriting any widget-bound ``st.session_state`` keys that
    are written too early. That behavior has previously triggered
    ``StreamlitAPIException`` errors and caused the wizard to lose follow-up
    completion state. Callers therefore must not set ``st.session_state``
    directly during layout; instead they should rely on the widget helper
    functions (which invoke ``_update_profile`` only after Streamlit stabilizes)
    so sidebar, summary, and export state stay in sync without regression risk.
    When ``sync_widget_state`` is ``False`` the session state mutation is
    skipped, which is useful for inline follow-up widgets that share keys with
    existing inputs.
    """

    try:
        data = _get_profile_state()
        data.setdefault("location", {})
        normalized_value_for_path = _normalize_value_for_path(path, value)
        normalized_value = _normalize_semantic_empty(normalized_value_for_path)

        def _sync_widget_state(new_value: Any) -> None:
            """Synchronise the widget-bound session value when needed."""

            if not sync_widget_state:
                return
            if new_value is _MISSING:
                st.session_state.pop(path, None)
                return
            current_session_value = st.session_state.get(path, _MISSING)
            if current_session_value is _MISSING or current_session_value != new_value:
                st.session_state[path] = new_value

        if normalized_value is None:
            if session_value is _MISSING:
                _sync_widget_state(_MISSING)
            else:
                _sync_widget_state(session_value)
        else:
            if session_value is _MISSING:
                target_session_value = normalized_value_for_path
            else:
                target_session_value = session_value
            _sync_widget_state(target_session_value)
        current = get_in(data, path)
        if _normalize_semantic_empty(current) != normalized_value:
            if normalized_value is None and not isinstance(
                normalized_value_for_path,
                (list, tuple, set, frozenset, dict),
            ):
                stored_value: Any = None
            else:
                stored_value = normalized_value_for_path
            set_in(data, path, stored_value)
            _clear_generated()
            _remove_field_lock_metadata(path)
            _sync_followup_completion(path, normalized_value_for_path, data)
    except (RerunException, StopException):  # pragma: no cover - Streamlit control flow
        raise
    except Exception as error:  # pragma: no cover - defensive guard
        _handle_profile_update_error(path, error)


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


def resolve_display_value(
    field_path: str,
    *,
    default: Any | None = None,
    formatter: Callable[[Any | None], str] | None = None,
) -> str:
    """Return the formatted display string for ``field_path``."""

    value = get_value(field_path)
    if value is None:
        value = default
    if formatter is not None:
        return formatter(value)
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _coerce_logo_bytes(data: Any) -> bytes | None:
    """Return ``data`` as ``bytes`` when it looks like a logo payload."""

    if isinstance(data, (bytes, bytearray)):
        return bytes(data)
    return None


def _extract_logo_brand_color(data: bytes | None) -> str | None:
    """Return a representative hex colour extracted from ``data`` when possible."""

    if not data:
        return None
    try:
        from PIL import Image
    except Exception:  # pragma: no cover - optional dependency
        return None

    try:
        with Image.open(io.BytesIO(data)) as img:
            img = img.convert("RGB")
            pixels = list(img.getdata())
    except Exception:  # pragma: no cover - defensive
        return None

    if not pixels:
        return None

    sample_size = min(len(pixels), 10_000)
    if sample_size <= 0:
        return None

    if len(pixels) > sample_size:
        step = max(len(pixels) // sample_size, 1)
        sampled = pixels[::step][:sample_size]
    else:
        sampled = pixels

    if not sampled:
        return None

    r_total = sum(pixel[0] for pixel in sampled)
    g_total = sum(pixel[1] for pixel in sampled)
    b_total = sum(pixel[2] for pixel in sampled)
    count = len(sampled)
    if count == 0:
        return None

    r_avg = int(r_total / count)
    g_avg = int(g_total / count)
    b_avg = int(b_total / count)
    return f"#{r_avg:02x}{g_avg:02x}{b_avg:02x}"


def _set_company_logo(data: bytes | bytearray | None) -> None:
    """Persist logo ``data`` under shared session keys for reuse."""

    logo_bytes = _coerce_logo_bytes(data)
    st.session_state[StateKeys.JOB_AD_LOGO_DATA] = logo_bytes
    st.session_state["company_logo"] = logo_bytes

    brand_color = _extract_logo_brand_color(logo_bytes)
    if brand_color:
        st.session_state[ProfilePaths.COMPANY_BRAND_COLOR] = brand_color
        _update_profile(ProfilePaths.COMPANY_BRAND_COLOR, brand_color)


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

    job_title = str(_get_profile_value(profile, ProfilePaths.POSITION_JOB_TITLE) or "").strip()
    if not job_title:
        return None, None, None

    country_raw = str(_get_profile_value(profile, ProfilePaths.LOCATION_COUNTRY) or "").strip()
    iso_country = country_to_iso2(country_raw) if country_raw else None
    benchmark_role = resolve_salary_role(job_title) or job_title
    bench_country = iso_country or (country_raw.upper() if country_raw else "US")
    benchmark = get_salary_benchmark(benchmark_role, bench_country)
    raw_range = str((benchmark or {}).get("salary_range") or "")
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


def _get_profile_value(profile: Mapping[str, Any], field_path: str) -> Any:
    """Return the nested value stored under ``field_path`` within ``profile``."""

    current: Any = profile
    for part in field_path.split("."):
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
        if current is None:
            return None
    return current


def _derive_salary_range_defaults(profile: Mapping[str, Any]) -> _SalaryRangeDefaults:
    """Compute slider defaults from profile or benchmark information."""

    current_min = _to_int(_get_profile_value(profile, "compensation.salary_min"))
    current_max = _to_int(_get_profile_value(profile, "compensation.salary_max"))
    current_currency = str(_get_profile_value(profile, "compensation.currency") or "").strip() or None

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
    "resolve_display_value",
    "_SalaryRangeDefaults",
    "_benchmark_salary_range",
    "_clamp_salary_value",
    "_coerce_logo_bytes",
    "_derive_salary_range_defaults",
    "_get_company_logo_bytes",
    "_infer_currency_from_range",
    "_parse_salary_range_text",
    "_autofill_was_rejected",
    "_load_autofill_decisions",
    "_record_autofill_rejection",
    "_store_autofill_decisions",
    "_update_profile",
    "_set_company_logo",
    "_to_int",
    "get_in",
    "merge_unique_items",
    "normalize_text_area_list",
    "set_in",
    "SALARY_SLIDER_MAX",
    "SALARY_SLIDER_MIN",
    "SALARY_SLIDER_STEP",
    "unique_normalized",
]
