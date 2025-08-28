"""Helpers for initializing Streamlit session state."""

from __future__ import annotations

import os

import streamlit as st

from constants.keys import StateKeys
from config import REASONING_EFFORT
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
    if "lang" not in st.session_state:
        st.session_state["lang"] = "de"
    if "model" not in st.session_state:
        st.session_state["model"] = os.getenv("OPENAI_MODEL", "gpt-5-nano")
    if "vector_store_id" not in st.session_state:
        st.session_state["vector_store_id"] = os.getenv("VECTOR_STORE_ID", "")
    if "auto_reask" not in st.session_state:
        st.session_state["auto_reask"] = True
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
