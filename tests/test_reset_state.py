"""Regression tests for :func:`state.reset_state`."""

import streamlit as st

from constants.keys import StateKeys, UIKeys
from state import ensure_state, reset_state


def test_reset_state_preserves_control_preferences() -> None:
    """Language, reasoning, and dark-mode selections should persist."""

    st.session_state.clear()
    ensure_state()

    st.session_state["lang"] = "de"
    st.session_state[UIKeys.LANG_SELECT] = "de"
    st.session_state[StateKeys.REASONING_MODE] = "precise"
    st.session_state[UIKeys.REASONING_MODE] = "precise"
    st.session_state["dark_mode"] = False
    st.session_state["ui.dark_mode"] = False

    reset_state()

    assert st.session_state["lang"] == "de"
    assert st.session_state[UIKeys.LANG_SELECT] == "de"
    assert st.session_state[StateKeys.REASONING_MODE] == "precise"
    assert st.session_state[UIKeys.REASONING_MODE] == "precise"
    assert st.session_state["dark_mode"] is False
    assert st.session_state["ui.dark_mode"] is False


def test_reset_state_rehydrates_lang_select_when_missing() -> None:
    """Missing UI language selectors should mirror the preserved base language."""

    st.session_state.clear()
    ensure_state()

    st.session_state["lang"] = "de"
    st.session_state.pop(UIKeys.LANG_SELECT, None)

    reset_state()

    assert st.session_state["lang"] == "de"
    assert st.session_state[UIKeys.LANG_SELECT] == "de"


def test_ensure_state_preserves_profile_on_preference_toggle() -> None:
    """Switching language or theme should not reset captured profile data."""

    st.session_state.clear()
    ensure_state()

    profile = st.session_state[StateKeys.PROFILE]
    profile.setdefault("company", {})["name"] = "ACME"
    st.session_state["lang"] = "de"
    st.session_state["ui.dark_mode"] = False
    st.session_state.pop("dark_mode", None)

    ensure_state()

    rehydrated = st.session_state[StateKeys.PROFILE]
    assert rehydrated["company"]["name"] == "ACME"
    assert st.session_state["lang"] == "de"
    assert st.session_state["dark_mode"] is False
    assert st.session_state["ui.dark_mode"] is False


def test_reset_state_clears_profile_and_followups() -> None:
    """Resetting the wizard should drop profile overrides and follow-up artifacts."""

    st.session_state.clear()
    ensure_state()

    st.session_state[StateKeys.PROFILE].setdefault("company", {})["name"] = "ACME"
    st.session_state[StateKeys.FOLLOWUPS] = [{"field": "company.name", "question": "Name?"}]
    st.session_state["fu_company.name"] = "pending"

    reset_state()

    profile = st.session_state[StateKeys.PROFILE]
    assert profile.get("company", {}).get("name") in {"", None}
    assert st.session_state[StateKeys.FOLLOWUPS] == []
    assert not any(key.startswith("fu_") for key in st.session_state)
