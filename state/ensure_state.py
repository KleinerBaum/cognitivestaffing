"""Helpers for initializing Streamlit session state."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from copy import deepcopy
from typing import Any, Callable
from urllib.parse import urlparse

import streamlit as st
from pydantic import ValidationError

from types import MappingProxyType

from constants.keys import StateKeys
from config import (
    GPT4O,
    OPENAI_BASE_URL,
    REASONING_EFFORT,
    VERBOSITY,
    normalise_model_name,
    normalise_model_override,
    normalise_verbosity,
)
from core.schema import (
    RecruitingWizard,
    canonicalize_profile_payload,
    canonicalize_wizard_payload,
    coerce_and_fill,
    coerce_and_fill_wizard,
    is_wizard_schema_enabled,
)
from models.need_analysis import NeedAnalysisProfile
from utils.normalization import normalize_profile


import config as app_config


logger = logging.getLogger(__name__)


_DEFAULT_STATE_FACTORIES: Mapping[str, Callable[[], Any]] = MappingProxyType(
    {
        StateKeys.RAW_TEXT: lambda: "",
        StateKeys.RAW_BLOCKS: list,
        StateKeys.STEP: lambda: 0,
        StateKeys.EXTRACTION_SUMMARY: dict,
        StateKeys.EXTRACTION_MISSING: list,
        StateKeys.EXTRACTION_RAW_PROFILE: dict,
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
        StateKeys.BOOLEAN_STR: lambda: "",
        StateKeys.INTERVIEW_GUIDE_MD: lambda: "",
        "lang": lambda: "en",
        "auto_reask": lambda: True,
        "auto_reask_round": lambda: 0,
        "auto_reask_total": lambda: 0,
        "dark_mode": lambda: True,
        "skip_intro": lambda: False,
        "wizard": lambda: {"current_step": "jobad"},
    }
)


def ensure_state() -> None:
    """Initialize ``st.session_state`` with required keys.

    Existing keys are preserved to respect user interactions or URL params.
    """

    existing = st.session_state.get(StateKeys.PROFILE)
    if is_wizard_schema_enabled():
        _ensure_wizard_profile(existing)
    elif not isinstance(existing, Mapping):
        st.session_state[StateKeys.PROFILE] = normalize_profile(NeedAnalysisProfile())
    else:
        try:
            profile = coerce_and_fill(existing)
            st.session_state[StateKeys.PROFILE] = normalize_profile(profile)
        except ValidationError as error:
            logger.debug("Validation error when coercing profile: %s", error)
            sanitized = _sanitize_profile(existing)
            try:
                validated = NeedAnalysisProfile.model_validate(sanitized)
                st.session_state[StateKeys.PROFILE] = normalize_profile(validated)
            except ValidationError as sanitized_error:
                logger.warning(
                    "Failed to sanitize profile data; resetting to defaults: %s",
                    sanitized_error,
                )
                st.session_state[StateKeys.PROFILE] = normalize_profile(NeedAnalysisProfile())
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
    if "model_override" not in st.session_state:
        st.session_state["model_override"] = ""
    else:
        override = normalise_model_override(st.session_state.get("model_override"))
        st.session_state["model_override"] = override or ""
    if "vector_store_id" not in st.session_state:
        st.session_state["vector_store_id"] = os.getenv("VECTOR_STORE_ID", "")
    if "openai_api_key_missing" not in st.session_state:
        st.session_state["openai_api_key_missing"] = not app_config.is_llm_enabled()
    if "llm_enabled" not in st.session_state:
        st.session_state["llm_enabled"] = app_config.is_llm_enabled()
    if "openai_base_url_invalid" not in st.session_state:
        if OPENAI_BASE_URL:
            parsed = urlparse(OPENAI_BASE_URL)
            st.session_state["openai_base_url_invalid"] = not (parsed.scheme and parsed.netloc)
        else:
            st.session_state["openai_base_url_invalid"] = False
    if "reasoning_effort" not in st.session_state:
        st.session_state["reasoning_effort"] = REASONING_EFFORT
    else:
        effort = st.session_state.get("reasoning_effort")
        st.session_state["reasoning_effort"] = effort if isinstance(effort, str) else REASONING_EFFORT
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
    wizard_state = st.session_state.get("wizard")
    if not isinstance(wizard_state, dict):
        st.session_state["wizard"] = {"current_step": "jobad"}
    else:
        wizard_state.setdefault("current_step", "jobad")


def _sanitize_profile(data: Mapping[str, Any]) -> dict[str, Any]:
    """Remove unsupported fields while preserving valid values."""

    canonical = canonicalize_profile_payload(data)
    template = NeedAnalysisProfile().model_dump()
    sanitized = deepcopy(template)
    _merge_known_fields(sanitized, canonical)
    return sanitized


def _ensure_wizard_profile(existing: Any) -> None:
    """Ensure the session profile uses the RecruitingWizard schema."""

    if not isinstance(existing, Mapping):
        st.session_state[StateKeys.PROFILE] = RecruitingWizard().model_dump(mode="json")
        return
    try:
        profile = coerce_and_fill_wizard(existing)
        st.session_state[StateKeys.PROFILE] = profile.model_dump(mode="json")
    except ValidationError as error:
        logger.debug("Validation error when coercing wizard profile: %s", error)
        sanitized = _sanitize_wizard_profile(existing)
        try:
            validated = RecruitingWizard.model_validate(sanitized)
            st.session_state[StateKeys.PROFILE] = validated.model_dump(mode="json")
        except ValidationError as sanitized_error:
            logger.warning(
                "Failed to sanitize wizard profile; resetting to defaults: %s",
                sanitized_error,
            )
            st.session_state[StateKeys.PROFILE] = RecruitingWizard().model_dump(mode="json")


def _sanitize_wizard_profile(data: Mapping[str, Any]) -> dict[str, Any]:
    """Remove unsupported fields for the RecruitingWizard schema."""

    canonical = canonicalize_wizard_payload(data)
    template = RecruitingWizard().model_dump(mode="json")
    sanitized = deepcopy(template)
    _merge_known_fields(sanitized, canonical)
    return sanitized


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


def reset_state() -> None:
    """Reset ``st.session_state`` while preserving basic user settings.

    Keeps language, model, vector store ID and auto-reask flag, then
    reinitializes defaults via :func:`ensure_state`.
    """

    preserve = {"lang", "model", "model_override", "vector_store_id", "auto_reask"}
    for key in list(st.session_state.keys()):
        if key not in preserve:
            del st.session_state[key]
    st.cache_data.clear()
    ensure_state()
