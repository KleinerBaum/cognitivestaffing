"""Helpers for initializing Streamlit session state."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping, MutableMapping
from copy import deepcopy
from typing import Any, Callable, Sequence
from urllib.parse import urlparse
from uuid import uuid4

import streamlit as st
from pydantic import ValidationError

from types import MappingProxyType

from constants.keys import ProfilePaths, StateKeys, UIKeys
from config import (
    GPT4O,
    OPENAI_BASE_URL,
    REASONING_EFFORT,
    VERBOSITY,
    normalise_model_name,
    normalise_verbosity,
)
from core.schema import (
    canonicalize_profile_payload,
    coerce_and_fill,
)
from models.need_analysis import NeedAnalysisProfile
from utils.normalization import NormalizedProfilePayload, normalize_profile
from utils.i18n import tr
from llm.json_repair import repair_profile_payload
from llm.profile_normalization import normalize_interview_stages_field
from utils.logging_context import configure_logging, set_model, set_session_id


import config as app_config


_LEGACY_PROFILE_KEY_ALIASES: Mapping[str, str] = MappingProxyType(
    {
        "company_name": ProfilePaths.COMPANY_NAME.value,
        "company_hq": ProfilePaths.COMPANY_HQ_LOCATION.value,
        "company_headquarters": ProfilePaths.COMPANY_HQ_LOCATION.value,
        "company_size": ProfilePaths.COMPANY_SIZE.value,
        "company_industry": ProfilePaths.COMPANY_INDUSTRY.value,
        "company_website": ProfilePaths.COMPANY_WEBSITE.value,
        "company_mission": ProfilePaths.COMPANY_MISSION.value,
        "company_culture": ProfilePaths.COMPANY_CULTURE.value,
        "contact_name": ProfilePaths.COMPANY_CONTACT_NAME.value,
        "contact_email": ProfilePaths.COMPANY_CONTACT_EMAIL.value,
        "contact_phone": ProfilePaths.COMPANY_CONTACT_PHONE.value,
        "hq_location": ProfilePaths.COMPANY_HQ_LOCATION.value,
        "primary_city": ProfilePaths.LOCATION_PRIMARY_CITY.value,
        "city": ProfilePaths.LOCATION_PRIMARY_CITY.value,
        "country": ProfilePaths.LOCATION_COUNTRY.value,
        "company_country": ProfilePaths.LOCATION_COUNTRY.value,
    }
)


logger = logging.getLogger(__name__)


_DEFAULT_STATE_FACTORIES: Mapping[str, Callable[[], Any]] = MappingProxyType(
    {
        StateKeys.RAW_TEXT: lambda: "",
        StateKeys.RAW_BLOCKS: list,
        StateKeys.STEP: lambda: 0,
        StateKeys.EXTRACTION_SUMMARY: dict,
        StateKeys.EXTRACTION_MISSING: list,
        StateKeys.EXTRACTION_RAW_PROFILE: dict,
        StateKeys.SESSION_ID: lambda: str(uuid4()),
        StateKeys.ESCO_SKILLS: list,
        StateKeys.ESCO_MISSING_SKILLS: list,
        StateKeys.EXTRACTION_ESCO_OCCUPATION_OPTIONS: list,
        StateKeys.UI_ESCO_OCCUPATION_OPTIONS: list,
        StateKeys.ESCO_SELECTED_OCCUPATIONS: list,
        StateKeys.SKILL_BUCKETS: lambda: {"must": [], "nice": []},
        StateKeys.FOLLOWUPS: list,
        StateKeys.COMPLETED_SECTIONS: list,
        StateKeys.FIRST_INCOMPLETE_SECTION: lambda: None,
        StateKeys.PENDING_INCOMPLETE_JUMP: lambda: False,
        StateKeys.WIZARD_STEP_COUNT: lambda: 0,
        StateKeys.WIZARD_AUTOFILL_DECISIONS: dict,
        StateKeys.COMPANY_PAGE_SUMMARIES: dict,
        StateKeys.COMPANY_PAGE_BASE: lambda: "",
        StateKeys.COMPANY_PAGE_TEXT_CACHE: dict,
        StateKeys.COMPANY_INFO_CACHE: dict,
        StateKeys.JOB_AD_SELECTED_FIELDS: set,
        StateKeys.JOB_AD_SELECTED_VALUES: dict,
        StateKeys.JOB_AD_MANUAL_ENTRIES: list,
        StateKeys.JOB_AD_SELECTED_AUDIENCE: lambda: "",
        StateKeys.JOB_AD_FONT_CHOICE: lambda: "Helvetica",
        StateKeys.JOB_AD_LOGO_DATA: lambda: None,
        StateKeys.INTERVIEW_AUDIENCE: lambda: "general",
        StateKeys.INTERVIEW_GUIDE_DATA: dict,
        StateKeys.JOB_AD_MD: lambda: "",
        StateKeys.JOB_AD_PREVIEW: lambda: "",
        StateKeys.BOOLEAN_STR: lambda: "",
        StateKeys.BOOLEAN_PREVIEW: lambda: "",
        StateKeys.INTERVIEW_GUIDE_MD: lambda: "",
        StateKeys.INTERVIEW_GUIDE_PREVIEW: lambda: "",
        StateKeys.AUTOSAVE_PROMPT_ACK: lambda: False,
        StateKeys.REASONING_EFFORT: lambda: REASONING_EFFORT,
        StateKeys.STEP_FAILURES: dict,
        StateKeys.STEP_AI_SKIPPED: list,
        "debug": lambda: False,
        UIKeys.DEBUG_DETAILS: lambda: False,
        UIKeys.DEBUG_API_MODE: lambda: "responses",
        "lang": lambda: "en",
        "auto_reask": lambda: True,
        "auto_reask_round": lambda: 0,
        "auto_reask_total": lambda: 0,
        "dark_mode": lambda: True,
        "skip_intro": lambda: False,
        "wizard": lambda: {"current_step": "jobad"},
    }
)


_PRESERVED_RESET_KEYS: frozenset[str] = frozenset(
    {
        "lang",
        UIKeys.LANG_SELECT,
        StateKeys.REASONING_MODE,
        UIKeys.REASONING_MODE,
        "dark_mode",
        "ui.dark_mode",
        "model",
        "vector_store_id",
        "auto_reask",
    }
)


_CRITICAL_PROFILE_DEFAULTS: Mapping[str, str] = MappingProxyType(
    {
        ProfilePaths.COMPANY_CONTACT_EMAIL.value: "",
        ProfilePaths.LOCATION_PRIMARY_CITY.value: "",
    }
)


def _is_meaningful(value: Any) -> bool:
    """Return ``True`` when ``value`` should override an existing field."""

    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, frozenset)):
        return bool(value)
    if isinstance(value, Mapping):
        return bool(value)
    return True


def _get_path(data: Mapping[str, Any], path: str) -> Any:
    """Return the value stored at ``path`` within ``data`` when available."""

    cursor: Any = data
    for part in path.split("."):
        if isinstance(cursor, Mapping) and part in cursor:
            cursor = cursor[part]
        else:
            return None
    return cursor


def _set_path(target: dict[str, Any], path: str, value: Any) -> None:
    """Assign ``value`` inside ``target`` following ``path`` segments."""

    cursor: dict[str, Any] = target
    parts = path.split(".")
    for part in parts[:-1]:
        next_value = cursor.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            cursor[part] = next_value
        cursor = next_value
    cursor[parts[-1]] = value


def _pop_casefold(source: Mapping[str, Any], key: str) -> tuple[bool, Any]:
    """Return and remove ``key`` from ``source`` irrespective of casing."""

    if not isinstance(source, dict):
        return False, None
    lower = key.casefold()
    for actual in list(source.keys()):
        if isinstance(actual, str) and actual.casefold() == lower:
            value = source.pop(actual)
            return True, value
    return False, None


def _migrate_legacy_profile_keys() -> None:
    """Promote legacy flat session keys to canonical profile paths."""

    session = st.session_state
    existing = session.get(StateKeys.PROFILE)
    profile: dict[str, Any]
    if isinstance(existing, Mapping):
        profile = dict(existing)
    else:
        profile = {}

    migrated = False
    for alias, canonical in _LEGACY_PROFILE_KEY_ALIASES.items():
        moved = False
        value: Any | None = None
        if alias in session:
            value = session.pop(alias)
            moved = True
        else:
            moved, value = _pop_casefold(profile, alias)
        if not moved or not _is_meaningful(value):
            continue
        current = _get_path(profile, canonical)
        if _is_meaningful(current):
            continue
        _set_path(profile, canonical, value)
        migrated = True

    if migrated or (profile and not isinstance(existing, Mapping)):
        session[StateKeys.PROFILE] = profile


def ensure_state() -> None:
    """Initialize ``st.session_state`` with required keys.

    Existing keys are preserved to respect user interactions or URL params.
    Profiles are normalised through :func:`coerce_and_fill` so all aliases
    collapse into the unified NeedAnalysis schema before widgets render. Legacy
    flat keys are upgraded via :func:`_migrate_legacy_profile_keys`.
    """

    configure_logging()
    session_id = st.session_state.get(StateKeys.SESSION_ID)
    if not isinstance(session_id, str) or not session_id.strip():
        session_id = str(uuid4())
        st.session_state[StateKeys.SESSION_ID] = session_id
    set_session_id(session_id)

    _migrate_legacy_profile_keys()
    existing = st.session_state.get(StateKeys.PROFILE)
    auto_populated_paths: list[str] = []
    removed_paths: list[str] = []
    if not isinstance(existing, Mapping):
        normalized_default: NormalizedProfilePayload = normalize_profile(NeedAnalysisProfile())
        ensured_default = _apply_critical_profile_defaults(normalized_default)
        st.session_state[StateKeys.PROFILE] = ensured_default
        _record_profile_repair_notice([], [])
    else:
        try:
            profile = coerce_and_fill(existing)
            normalized_profile: NormalizedProfilePayload = normalize_profile(profile)
            ensured_profile = _apply_critical_profile_defaults(normalized_profile, auto_populated_paths)
            st.session_state[StateKeys.PROFILE] = ensured_profile
            _record_profile_repair_notice(auto_populated_paths, removed_paths)
        except ValidationError as error:
            logger.debug("Validation error when coercing profile: %s", error)
            sanitized = _sanitize_profile(existing)
            try:
                validated = NeedAnalysisProfile.model_validate(sanitized)
                normalized_validated: NormalizedProfilePayload = normalize_profile(validated)
                ensured_validated = _apply_critical_profile_defaults(normalized_validated, auto_populated_paths)
                st.session_state[StateKeys.PROFILE] = ensured_validated
                _record_profile_repair_notice(auto_populated_paths, removed_paths)
            except ValidationError as sanitized_error:
                errors = sanitized_error.errors()
                targeted_profile, patched_paths = _fix_known_profile_fields(sanitized, errors)
                auto_populated_paths.extend(patched_paths)
                if patched_paths:
                    try:
                        validated = NeedAnalysisProfile.model_validate(targeted_profile)
                        normalized_validated = normalize_profile(validated)
                        ensured_validated = _apply_critical_profile_defaults(normalized_validated, auto_populated_paths)
                        st.session_state[StateKeys.PROFILE] = ensured_validated
                        logger.info(
                            "Patched invalid profile fields in-place: %s",
                            ", ".join(patched_paths),
                        )
                        _record_profile_repair_notice(auto_populated_paths, removed_paths)
                        return
                    except ValidationError as targeted_error:
                        logger.debug(
                            "Validation failed after targeted repairs: %s",
                            targeted_error,
                        )
                repaired_profile = _attempt_profile_repair(sanitized, errors)
                if repaired_profile is not None:
                    auto_populated_paths.extend(_summarize_error_locations(errors))
                    try:
                        validated = NeedAnalysisProfile.model_validate(repaired_profile)
                        normalized_validated = normalize_profile(validated)
                        ensured_validated = _apply_critical_profile_defaults(normalized_validated, auto_populated_paths)
                        st.session_state[StateKeys.PROFILE] = ensured_validated
                        logger.info(
                            "Repaired invalid profile fields: %s",
                            ", ".join(_summarize_error_locations(errors)),
                        )
                        _record_profile_repair_notice(auto_populated_paths, removed_paths)
                        return
                    except ValidationError as repair_error:
                        logger.debug(
                            "Validation failed after repair attempt: %s",
                            repair_error,
                        )
                trimmed_profile, removed_paths = _prune_invalid_profile_fields(sanitized, errors)
                if removed_paths:
                    try:
                        validated = NeedAnalysisProfile.model_validate(trimmed_profile)
                        normalized_validated = normalize_profile(validated)
                        ensured_validated = _apply_critical_profile_defaults(normalized_validated, auto_populated_paths)
                        st.session_state[StateKeys.PROFILE] = ensured_validated
                        logger.warning(
                            "Removed invalid profile fields: %s",
                            ", ".join(removed_paths),
                        )
                        _record_profile_repair_notice(auto_populated_paths, removed_paths)
                        return
                    except ValidationError as trimmed_error:
                        logger.debug(
                            "Validation failed after dropping invalid fields: %s",
                            trimmed_error,
                        )
                logger.warning(
                    "Unable to recover profile data after repair attempts; resetting to defaults.",
                )
                _record_profile_reset_warning(errors)
                fallback_profile: NormalizedProfilePayload = normalize_profile(NeedAnalysisProfile())
                auto_populated_paths.extend(_summarize_error_locations(errors))
                ensured_fallback = _apply_critical_profile_defaults(fallback_profile, auto_populated_paths)
                st.session_state[StateKeys.PROFILE] = ensured_fallback
                _record_profile_repair_notice(auto_populated_paths, removed_paths)
    for key, factory in _DEFAULT_STATE_FACTORIES.items():
        if key not in st.session_state:
            st.session_state[key] = factory()
    canonical_model = normalise_model_name(app_config.OPENAI_MODEL) or GPT4O
    if app_config.OPENAI_MODEL != canonical_model:
        app_config.OPENAI_MODEL = canonical_model

    if "model" not in st.session_state:
        st.session_state["model"] = canonical_model
    else:
        current_model = normalise_model_name(st.session_state.get("model"))
        st.session_state["model"] = current_model or canonical_model
    if "model_override" in st.session_state:
        del st.session_state["model_override"]
    set_model(canonical_model)
    if "vector_store_id" not in st.session_state:
        st.session_state["vector_store_id"] = os.getenv("VECTOR_STORE_ID", "")
    if "openai_api_key_missing" not in st.session_state:
        st.session_state["openai_api_key_missing"] = not app_config.is_llm_enabled()
    if "openai_unavailable" not in st.session_state:
        st.session_state["openai_unavailable"] = False
    if "openai_unavailable_reason" not in st.session_state:
        st.session_state["openai_unavailable_reason"] = ""
    if "llm_enabled" not in st.session_state:
        st.session_state["llm_enabled"] = app_config.is_llm_enabled()
    if "openai_base_url_invalid" not in st.session_state:
        if OPENAI_BASE_URL:
            parsed = urlparse(OPENAI_BASE_URL)
            st.session_state["openai_base_url_invalid"] = not (parsed.scheme and parsed.netloc)
        else:
            st.session_state["openai_base_url_invalid"] = False
    if StateKeys.REASONING_EFFORT not in st.session_state:
        st.session_state[StateKeys.REASONING_EFFORT] = REASONING_EFFORT
    else:
        effort = st.session_state.get(StateKeys.REASONING_EFFORT)
        st.session_state[StateKeys.REASONING_EFFORT] = effort if isinstance(effort, str) else REASONING_EFFORT

    st.session_state[StateKeys.EXTRACTION_STRICT_FORMAT] = True
    st.session_state[UIKeys.EXTRACTION_STRICT_FORMAT] = True

    preferred_mode = "precise" if REASONING_EFFORT not in {"none", "minimal", "low"} else "quick"
    if StateKeys.REASONING_MODE not in st.session_state:
        st.session_state[StateKeys.REASONING_MODE] = preferred_mode
    else:
        raw_mode = st.session_state.get(StateKeys.REASONING_MODE)
        if isinstance(raw_mode, str):
            normalised_mode = raw_mode.strip().lower()
            if normalised_mode not in {"quick", "precise"}:
                st.session_state[StateKeys.REASONING_MODE] = preferred_mode
        else:
            st.session_state[StateKeys.REASONING_MODE] = preferred_mode
    if "verbosity" not in st.session_state:
        st.session_state["verbosity"] = VERBOSITY
    else:
        current_verbosity = normalise_verbosity(st.session_state.get("verbosity"), default=VERBOSITY)
        st.session_state["verbosity"] = current_verbosity
    if StateKeys.USAGE not in st.session_state:
        st.session_state[StateKeys.USAGE] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "by_task": {},
        }
    else:
        usage_state = st.session_state[StateKeys.USAGE]
        usage_state.setdefault("input_tokens", 0)
        usage_state.setdefault("output_tokens", 0)
        usage_state.setdefault("by_task", {})
    if StateKeys.USAGE_BUDGET_EXCEEDED not in st.session_state:
        st.session_state[StateKeys.USAGE_BUDGET_EXCEEDED] = False
    wizard_state = st.session_state.get("wizard")
    if not isinstance(wizard_state, dict):
        st.session_state["wizard"] = {"current_step": "jobad"}
    else:
        wizard_state.setdefault("current_step", "jobad")

    _rehydrate_control_preferences()


def _sanitize_profile(data: Mapping[str, Any]) -> dict[str, Any]:
    """Remove unsupported fields while preserving valid values."""

    canonical = canonicalize_profile_payload(data)
    template = NeedAnalysisProfile().model_dump()
    sanitized = deepcopy(template)
    _merge_known_fields(sanitized, canonical)
    return sanitized


def _attempt_profile_repair(
    payload: Mapping[str, Any], errors: Sequence[Mapping[str, Any]] | None
) -> Mapping[str, Any] | None:
    """Attempt to fix ``payload`` using the JSON repair helper."""

    try:
        repaired = repair_profile_payload(payload, errors=errors)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.debug("Profile repair helper failed: %s", exc)
        return None
    if not repaired:
        return None
    if not isinstance(repaired, Mapping):
        return None
    return dict(repaired)


def _summarize_error_locations(
    errors: Sequence[Mapping[str, Any]] | None,
) -> tuple[str, ...]:
    """Return unique dotted paths describing the provided validation errors."""

    if not errors:
        return ("<root>",)
    seen: set[str] = set()
    summary: list[str] = []
    for entry in errors:
        loc = entry.get("loc")
        if not isinstance(loc, (list, tuple)):
            continue
        label = _format_error_location(loc)
        if not label:
            label = "<root>"
        if label in seen:
            continue
        seen.add(label)
        summary.append(label)
    if not summary:
        return ("<root>",)
    return tuple(summary)


def _record_profile_reset_warning(errors: Sequence[Mapping[str, Any]] | None) -> None:
    """Persist a bilingual warning whenever the profile falls back to defaults."""

    lang = st.session_state.get("lang")
    warning_message = tr(
        "⚠️ Profil konnte nicht validiert werden – bitte Felder manuell prüfen.",
        "⚠️ Extracted profile could not be validated – please review the fields manually.",
        lang=lang,
    )
    summary: dict[str, str] = {
        tr("Status", "Status", lang=lang): warning_message,
    }
    impacted = [label for label in _summarize_error_locations(errors) if label != "<root>"]
    if impacted:
        summary[tr("Betroffene Felder", "Impacted fields", lang=lang)] = ", ".join(impacted)
    st.session_state[StateKeys.EXTRACTION_SUMMARY] = summary
    st.session_state[StateKeys.STEPPER_WARNING] = warning_message


def _record_profile_repair_notice(auto_populated_paths: Sequence[str], removed_paths: Sequence[str]) -> None:
    """Store schema paths that were auto-filled or removed during repair."""

    unique_auto = tuple(dict.fromkeys(path for path in auto_populated_paths if path))
    unique_removed = tuple(dict.fromkeys(path for path in removed_paths if path))
    if not unique_auto and not unique_removed:
        st.session_state.pop(StateKeys.PROFILE_REPAIR_FIELDS, None)
        return
    st.session_state[StateKeys.PROFILE_REPAIR_FIELDS] = {
        "auto_populated": list(unique_auto),
        "removed": list(unique_removed),
    }


def _format_error_location(location: Sequence[Any]) -> str:
    """Return a dotted representation for a validation ``location`` path."""

    if not location:
        return ""
    formatted: list[str] = []
    for part in location:
        if isinstance(part, int):
            if not formatted:
                formatted.append(f"[{part}]")
            else:
                formatted[-1] = f"{formatted[-1]}[{part}]"
            continue
        formatted.append(str(part))
    return ".".join(formatted)


def _fix_known_profile_fields(
    payload: Mapping[str, Any], errors: Sequence[Mapping[str, Any]] | None
) -> tuple[dict[str, Any], list[str]]:
    """Return a patched copy of ``payload`` for known validation issues."""

    if isinstance(payload, dict):
        patched: dict[str, Any] = deepcopy(payload)
    else:
        patched = deepcopy(dict(payload))
    if not errors:
        return patched, []
    fixed_paths: list[str] = []
    seen: set[str] = set()
    for entry in errors:
        loc = entry.get("loc")
        if not isinstance(loc, (list, tuple)) or not loc:
            continue
        label = _format_error_location(loc) or "<root>"
        if label in seen:
            continue
        if _apply_known_field_fix(patched, loc):
            fixed_paths.append(label)
            seen.add(label)
    return patched, fixed_paths


def _apply_known_field_fix(target: MutableMapping[str, Any], location: Sequence[Any]) -> bool:
    """Attempt to apply a targeted fix for ``location`` within ``target``."""

    if len(location) >= 2 and tuple(location[:2]) == ("process", "interview_stages"):
        return _fix_interview_stages_field(target)
    if len(location) >= 2 and tuple(location[:2]) == ("company", "contact_email"):
        return _fix_contact_email_field(target)
    return False


def _fix_interview_stages_field(target: MutableMapping[str, Any]) -> bool:
    """Normalise ``process.interview_stages`` so it is never a list."""

    process = target.get("process")
    if not isinstance(process, MutableMapping):
        return False
    before = process.get("interview_stages")
    normalize_interview_stages_field(target)
    after = process.get("interview_stages")
    return before != after


def _fix_contact_email_field(target: MutableMapping[str, Any]) -> bool:
    """Provide a blank default for invalid ``company.contact_email`` values."""

    company = target.get("company")
    if not isinstance(company, MutableMapping):
        return False
    current = company.get("contact_email")
    if current == "":
        return False
    company["contact_email"] = ""
    return True


def _prune_invalid_profile_fields(
    payload: Mapping[str, Any],
    errors: Sequence[Mapping[str, Any]] | None,
) -> tuple[dict[str, Any], list[str]]:
    """Remove invalid paths reported by ``errors`` from ``payload``."""

    copied = deepcopy(payload)
    if isinstance(copied, dict):
        mutable: dict[str, Any] = copied
    else:
        mutable = dict(copied)
    removed: list[str] = []
    seen: set[str] = set()
    if not errors:
        return mutable, removed
    for entry in errors:
        loc = entry.get("loc")
        if not isinstance(loc, (list, tuple)) or not loc:
            continue
        label = _format_error_location(loc)
        if not label:
            label = "<root>"
        if label in seen:
            continue
        removed_successfully = _remove_location_value(mutable, loc)
        if not removed_successfully:
            continue
        seen.add(label)
        removed.append(label)
    return mutable, removed


def _remove_location_value(target: Any, location: Sequence[Any]) -> bool:
    """Remove the value referenced by ``location`` from ``target`` when possible."""

    cursor: Any = target
    for index, part in enumerate(location):
        is_last = index == len(location) - 1
        if is_last:
            if isinstance(part, int) and isinstance(cursor, list):
                if 0 <= part < len(cursor):
                    del cursor[part]
                    return True
                return False
            if isinstance(part, str) and isinstance(cursor, dict):
                if part in cursor:
                    cursor.pop(part)
                    return True
                return False
            return False
        if isinstance(part, int):
            if isinstance(cursor, list) and 0 <= part < len(cursor):
                cursor = cursor[part]
            else:
                return False
        else:
            if isinstance(cursor, dict) and part in cursor:
                cursor = cursor[part]
            else:
                return False
    return False


def _merge_known_fields(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    """Merge ``source`` into ``target`` while ignoring unknown keys."""

    for key, value in source.items():
        if key not in target:
            continue
        current = target[key]
        if isinstance(current, dict) and isinstance(value, Mapping):
            _merge_known_fields(current, value)
        else:
            target[key] = value


def _apply_critical_profile_defaults(
    profile: NormalizedProfilePayload, inserted_paths: list[str] | None = None
) -> NormalizedProfilePayload:
    """Ensure critical profile fields always exist for downstream consumers."""

    for path, default in _CRITICAL_PROFILE_DEFAULTS.items():
        cursor: Any = profile
        segments = path.split(".")
        for segment in segments[:-1]:
            next_value = cursor.get(segment)
            if not isinstance(next_value, dict):
                next_value = {}
                cursor[segment] = next_value
            cursor = next_value
        leaf = segments[-1]
        value = cursor.get(leaf)
        if value is None:
            cursor[leaf] = default
            if inserted_paths is not None:
                inserted_paths.append(path)
            continue
        if isinstance(value, str) and not value:
            cursor[leaf] = default
            if inserted_paths is not None:
                inserted_paths.append(path)
    return profile


def reset_state() -> None:
    """Reset ``st.session_state`` while preserving basic user settings."""

    _clear_followup_session_state()

    preserved: dict[str, Any] = {key: st.session_state[key] for key in _PRESERVED_RESET_KEYS if key in st.session_state}

    st.session_state.clear()
    st.session_state.update(preserved)

    st.cache_data.clear()
    ensure_state()
    _rehydrate_control_preferences()


def _clear_followup_session_state() -> None:
    """Remove inline follow-up state so resets never resurrect stale prompts."""

    st.session_state.pop(StateKeys.FOLLOWUPS, None)
    st.session_state.pop(StateKeys.FOLLOWUPS_RESPONSE_ID, None)
    followup_keys = [key for key in st.session_state.keys() if isinstance(key, str) and key.startswith("fu_")]
    for key in followup_keys:
        st.session_state.pop(key, None)


def _rehydrate_control_preferences() -> None:
    """Mirror preserved base preferences into UI-specific keys."""

    lang = st.session_state.get("lang")
    if isinstance(lang, str) and lang:
        st.session_state[UIKeys.LANG_SELECT] = lang

    reasoning_mode = st.session_state.get(StateKeys.REASONING_MODE)
    if isinstance(reasoning_mode, str) and reasoning_mode:
        st.session_state[UIKeys.REASONING_MODE] = reasoning_mode

    ui_dark_mode = st.session_state.get("ui.dark_mode")
    dark_mode = st.session_state.get("dark_mode")
    if isinstance(ui_dark_mode, bool):
        st.session_state["dark_mode"] = ui_dark_mode
    elif isinstance(dark_mode, bool):
        st.session_state["ui.dark_mode"] = dark_mode
