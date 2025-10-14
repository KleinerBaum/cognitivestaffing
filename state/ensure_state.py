"""Helpers for initializing Streamlit session state."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from copy import deepcopy
from typing import Any
from urllib.parse import urlparse

import streamlit as st
from pydantic import ValidationError

from constants.keys import StateKeys
from config import (
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    REASONING_EFFORT,
    OPENAI_MODEL,
    normalise_model_name,
    normalise_model_override,
)
from core.schema import ALIASES, coerce_and_fill
from models.need_analysis import NeedAnalysisProfile


logger = logging.getLogger(__name__)


def ensure_state() -> None:
    """Initialize ``st.session_state`` with required keys.

    Existing keys are preserved to respect user interactions or URL params.
    """

    existing = st.session_state.get(StateKeys.PROFILE)
    if not isinstance(existing, Mapping):
        st.session_state[StateKeys.PROFILE] = NeedAnalysisProfile().model_dump()
    else:
        try:
            st.session_state[StateKeys.PROFILE] = coerce_and_fill(existing).model_dump()
        except ValidationError as error:
            logger.debug("Validation error when coercing profile: %s", error)
            sanitized = _sanitize_profile(existing)
            try:
                st.session_state[StateKeys.PROFILE] = NeedAnalysisProfile.model_validate(sanitized).model_dump()
            except ValidationError as sanitized_error:
                logger.warning(
                    "Failed to sanitize profile data; resetting to defaults: %s",
                    sanitized_error,
                )
                st.session_state[StateKeys.PROFILE] = NeedAnalysisProfile().model_dump()
    if StateKeys.RAW_TEXT not in st.session_state:
        st.session_state[StateKeys.RAW_TEXT] = ""
    if StateKeys.RAW_BLOCKS not in st.session_state:
        st.session_state[StateKeys.RAW_BLOCKS] = []
    if StateKeys.STEP not in st.session_state:
        st.session_state[StateKeys.STEP] = 0
    if StateKeys.EXTRACTION_SUMMARY not in st.session_state:
        st.session_state[StateKeys.EXTRACTION_SUMMARY] = {}
    if StateKeys.EXTRACTION_MISSING not in st.session_state:
        st.session_state[StateKeys.EXTRACTION_MISSING] = []
    if StateKeys.EXTRACTION_RAW_PROFILE not in st.session_state:
        st.session_state[StateKeys.EXTRACTION_RAW_PROFILE] = {}
    if StateKeys.ESCO_SKILLS not in st.session_state:
        st.session_state[StateKeys.ESCO_SKILLS] = []
    if StateKeys.ESCO_MISSING_SKILLS not in st.session_state:
        st.session_state[StateKeys.ESCO_MISSING_SKILLS] = []
    if StateKeys.ESCO_OCCUPATION_OPTIONS not in st.session_state:
        st.session_state[StateKeys.ESCO_OCCUPATION_OPTIONS] = []
    if StateKeys.ESCO_SELECTED_OCCUPATIONS not in st.session_state:
        st.session_state[StateKeys.ESCO_SELECTED_OCCUPATIONS] = []
    if StateKeys.SKILL_BUCKETS not in st.session_state:
        st.session_state[StateKeys.SKILL_BUCKETS] = {"must": [], "nice": []}
    if StateKeys.FOLLOWUPS not in st.session_state:
        st.session_state[StateKeys.FOLLOWUPS] = []
    if StateKeys.COMPLETED_SECTIONS not in st.session_state:
        st.session_state[StateKeys.COMPLETED_SECTIONS] = []
    if StateKeys.FIRST_INCOMPLETE_SECTION not in st.session_state:
        st.session_state[StateKeys.FIRST_INCOMPLETE_SECTION] = None
    if StateKeys.PENDING_INCOMPLETE_JUMP not in st.session_state:
        st.session_state[StateKeys.PENDING_INCOMPLETE_JUMP] = False
    if StateKeys.WIZARD_STEP_COUNT not in st.session_state:
        st.session_state[StateKeys.WIZARD_STEP_COUNT] = 0
    if StateKeys.AUTOFILL_DECISIONS not in st.session_state:
        st.session_state[StateKeys.AUTOFILL_DECISIONS] = {}
    if StateKeys.COMPANY_PAGE_SUMMARIES not in st.session_state:
        st.session_state[StateKeys.COMPANY_PAGE_SUMMARIES] = {}
    if StateKeys.COMPANY_PAGE_BASE not in st.session_state:
        st.session_state[StateKeys.COMPANY_PAGE_BASE] = ""
    if StateKeys.COMPANY_PAGE_TEXT_CACHE not in st.session_state:
        st.session_state[StateKeys.COMPANY_PAGE_TEXT_CACHE] = {}
    if StateKeys.JOB_AD_SELECTED_FIELDS not in st.session_state:
        st.session_state[StateKeys.JOB_AD_SELECTED_FIELDS] = set()
    if StateKeys.JOB_AD_SELECTED_VALUES not in st.session_state:
        st.session_state[StateKeys.JOB_AD_SELECTED_VALUES] = {}
    if StateKeys.JOB_AD_MANUAL_ENTRIES not in st.session_state:
        st.session_state[StateKeys.JOB_AD_MANUAL_ENTRIES] = []
    if StateKeys.JOB_AD_SELECTED_AUDIENCE not in st.session_state:
        st.session_state[StateKeys.JOB_AD_SELECTED_AUDIENCE] = ""
    if StateKeys.JOB_AD_FONT_CHOICE not in st.session_state:
        st.session_state[StateKeys.JOB_AD_FONT_CHOICE] = "Helvetica"
    if StateKeys.JOB_AD_LOGO_DATA not in st.session_state:
        st.session_state[StateKeys.JOB_AD_LOGO_DATA] = None
    if StateKeys.INTERVIEW_AUDIENCE not in st.session_state:
        st.session_state[StateKeys.INTERVIEW_AUDIENCE] = "general"
    if StateKeys.INTERVIEW_GUIDE_DATA not in st.session_state:
        st.session_state[StateKeys.INTERVIEW_GUIDE_DATA] = {}
    if "lang" not in st.session_state:
        st.session_state["lang"] = "en"
    if "model" not in st.session_state:
        st.session_state["model"] = OPENAI_MODEL
    else:
        current_model = normalise_model_name(st.session_state.get("model"))
        st.session_state["model"] = current_model or OPENAI_MODEL
    if "model_override" not in st.session_state:
        st.session_state["model_override"] = ""
    else:
        override = normalise_model_override(st.session_state.get("model_override"))
        st.session_state["model_override"] = override or ""
    if "vector_store_id" not in st.session_state:
        st.session_state["vector_store_id"] = os.getenv("VECTOR_STORE_ID", "")
    if "openai_api_key_missing" not in st.session_state:
        st.session_state["openai_api_key_missing"] = not OPENAI_API_KEY
    if "openai_base_url_invalid" not in st.session_state:
        if OPENAI_BASE_URL:
            parsed = urlparse(OPENAI_BASE_URL)
            st.session_state["openai_base_url_invalid"] = not (parsed.scheme and parsed.netloc)
        else:
            st.session_state["openai_base_url_invalid"] = False
    if "auto_reask" not in st.session_state:
        st.session_state["auto_reask"] = True
    if "auto_reask_round" not in st.session_state:
        st.session_state["auto_reask_round"] = 0
    if "auto_reask_total" not in st.session_state:
        st.session_state["auto_reask_total"] = 0
    if "reasoning_effort" not in st.session_state:
        st.session_state["reasoning_effort"] = REASONING_EFFORT
    if "dark_mode" not in st.session_state:
        st.session_state["dark_mode"] = True
    if "skip_intro" not in st.session_state:
        st.session_state["skip_intro"] = False
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
    for key in (
        StateKeys.JOB_AD_MD,
        StateKeys.BOOLEAN_STR,
        StateKeys.INTERVIEW_GUIDE_MD,
    ):
        if key not in st.session_state:
            st.session_state[key] = ""


def _sanitize_profile(data: Mapping[str, Any]) -> dict[str, Any]:
    """Remove unsupported fields while preserving valid values."""

    canonical = _apply_aliases(data)
    template = NeedAnalysisProfile().model_dump()
    sanitized = deepcopy(template)
    _merge_known_fields(sanitized, canonical)
    return sanitized


def _apply_aliases(data: Mapping[str, Any]) -> dict[str, Any]:
    """Expand profile aliases to their canonical paths."""

    mutable = _to_mutable_dict(data)
    sentinel = object()
    for alias, target in ALIASES.items():
        value = _pop_path(mutable, alias, sentinel)
        if value is not sentinel:
            _set_path(mutable, target, value)
    return mutable


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


def _to_mutable_dict(data: Any) -> Any:
    """Convert mappings to plain dictionaries for mutation."""

    if isinstance(data, Mapping):
        return {key: _to_mutable_dict(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_to_mutable_dict(item) for item in data]
    return data


def _pop_path(obj: dict[str, Any], path: str, default: Any) -> Any:
    """Pop a dotted path from ``obj`` if present."""

    parts = path.split(".")
    cursor: Any = obj
    for part in parts[:-1]:
        if not isinstance(cursor, dict):
            return default
        if part not in cursor:
            return default
        cursor = cursor[part]
    if not isinstance(cursor, dict):
        return default
    return cursor.pop(parts[-1], default)


def _set_path(obj: dict[str, Any], path: str, value: Any) -> None:
    """Set ``value`` at ``path`` within ``obj`` creating nested dictionaries."""

    parts = path.split(".")
    cursor: Any = obj
    for part in parts[:-1]:
        next_value = cursor.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            cursor[part] = next_value
        cursor = next_value
    cursor[parts[-1]] = value


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
