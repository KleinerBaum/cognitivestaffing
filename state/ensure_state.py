"""Helpers for initializing Streamlit session state."""

from __future__ import annotations

import os
from urllib.parse import urlparse

import streamlit as st

from constants.keys import StateKeys
from config import OPENAI_API_KEY, OPENAI_BASE_URL, REASONING_EFFORT, OPENAI_MODEL
from models.need_analysis import NeedAnalysisProfile


def ensure_state() -> None:
    """Initialize ``st.session_state`` with required keys.

    Existing keys are preserved to respect user interactions or URL params.
    """

    if StateKeys.PROFILE not in st.session_state:
        st.session_state[StateKeys.PROFILE] = NeedAnalysisProfile().model_dump()
    if StateKeys.RAW_TEXT not in st.session_state:
        st.session_state[StateKeys.RAW_TEXT] = ""
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
    if StateKeys.ESCO_OCCUPATION_OPTIONS not in st.session_state:
        st.session_state[StateKeys.ESCO_OCCUPATION_OPTIONS] = []
    if StateKeys.SKILL_BUCKETS not in st.session_state:
        st.session_state[StateKeys.SKILL_BUCKETS] = {"must": [], "nice": []}
    if StateKeys.FOLLOWUPS not in st.session_state:
        st.session_state[StateKeys.FOLLOWUPS] = []
    if StateKeys.COMPANY_PAGE_SUMMARIES not in st.session_state:
        st.session_state[StateKeys.COMPANY_PAGE_SUMMARIES] = {}
    if StateKeys.COMPANY_PAGE_BASE not in st.session_state:
        st.session_state[StateKeys.COMPANY_PAGE_BASE] = ""
    if StateKeys.JOB_AD_SELECTED_FIELDS not in st.session_state:
        st.session_state[StateKeys.JOB_AD_SELECTED_FIELDS] = set()
    if StateKeys.JOB_AD_MANUAL_ENTRIES not in st.session_state:
        st.session_state[StateKeys.JOB_AD_MANUAL_ENTRIES] = []
    if StateKeys.JOB_AD_SELECTED_AUDIENCE not in st.session_state:
        st.session_state[StateKeys.JOB_AD_SELECTED_AUDIENCE] = ""
    if StateKeys.JOB_AD_FONT_CHOICE not in st.session_state:
        st.session_state[StateKeys.JOB_AD_FONT_CHOICE] = "Helvetica"
    if StateKeys.JOB_AD_LOGO_DATA not in st.session_state:
        st.session_state[StateKeys.JOB_AD_LOGO_DATA] = None
    if "lang" not in st.session_state:
        st.session_state["lang"] = "de"
    if "model" not in st.session_state:
        st.session_state["model"] = OPENAI_MODEL
    if "model_override" not in st.session_state:
        st.session_state["model_override"] = ""
    if "vector_store_id" not in st.session_state:
        st.session_state["vector_store_id"] = os.getenv("VECTOR_STORE_ID", "")
    if "openai_api_key_missing" not in st.session_state:
        st.session_state["openai_api_key_missing"] = not OPENAI_API_KEY
    if "openai_base_url_invalid" not in st.session_state:
        if OPENAI_BASE_URL:
            parsed = urlparse(OPENAI_BASE_URL)
            st.session_state["openai_base_url_invalid"] = not (
                parsed.scheme and parsed.netloc
            )
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
        st.session_state[StateKeys.USAGE] = {"input_tokens": 0, "output_tokens": 0}
    for key in (
        StateKeys.JOB_AD_MD,
        StateKeys.BOOLEAN_STR,
        StateKeys.INTERVIEW_GUIDE_MD,
    ):
        if key not in st.session_state:
            st.session_state[key] = ""


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
