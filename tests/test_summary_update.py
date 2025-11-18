"""Tests for editable summary helpers."""

from __future__ import annotations

import streamlit as st

from constants.keys import StateKeys, UIKeys
from tests.utils import ProfileDict
from wizard import _update_profile


def test_update_profile_clears_generated() -> None:
    """Updating profile fields clears derived outputs."""
    st.session_state.clear()
    profile: ProfileDict = {"company": {"name": "Old"}}
    st.session_state[StateKeys.PROFILE] = profile
    st.session_state[StateKeys.JOB_AD_MD] = "old"
    st.session_state[StateKeys.BOOLEAN_STR] = "old"
    st.session_state[StateKeys.INTERVIEW_GUIDE_MD] = "old"
    st.session_state[StateKeys.INTERVIEW_GUIDE_DATA] = {"metadata": {}}
    st.session_state[UIKeys.JOB_AD_OUTPUT] = "ui-old"
    st.session_state[UIKeys.INTERVIEW_OUTPUT] = "ui-old"

    _update_profile("company.name", "New")

    assert st.session_state[StateKeys.PROFILE]["company"]["name"] == "New"
    assert StateKeys.JOB_AD_MD not in st.session_state
    assert StateKeys.BOOLEAN_STR not in st.session_state
    assert StateKeys.INTERVIEW_GUIDE_MD not in st.session_state
    assert StateKeys.INTERVIEW_GUIDE_DATA not in st.session_state
    assert UIKeys.JOB_AD_OUTPUT not in st.session_state
    assert UIKeys.INTERVIEW_OUTPUT not in st.session_state


def test_update_profile_ignores_semantic_empty() -> None:
    """Setting empty values keeps cached outputs intact."""

    st.session_state.clear()
    profile: ProfileDict = {"company": {"brand_keywords": None}}
    st.session_state[StateKeys.PROFILE] = profile
    st.session_state[StateKeys.JOB_AD_MD] = "cached"

    _update_profile("company.brand_keywords", "")

    assert st.session_state[StateKeys.PROFILE]["company"]["brand_keywords"] is None
    assert st.session_state[StateKeys.JOB_AD_MD] == "cached"
