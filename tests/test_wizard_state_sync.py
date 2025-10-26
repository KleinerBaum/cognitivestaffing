"""Tests for synchronising profile updates with session state."""

import streamlit as st

from constants.keys import StateKeys
from state import ensure_state
from wizard import _update_profile


def test_update_profile_syncs_direct_session_state() -> None:
    """Updating the profile should reflect in ``st.session_state``."""

    st.session_state.clear()
    ensure_state()

    _update_profile("company.contact_phone", "+49 30 1234567")

    assert st.session_state["company.contact_phone"] == "+49 30 1234567"
    profile = st.session_state[StateKeys.PROFILE]
    assert profile["company"]["contact_phone"] == "+49 30 1234567"


def test_update_profile_normalizes_country_in_state() -> None:
    """Country updates should be normalised and synced to state."""

    st.session_state.clear()
    ensure_state()

    _update_profile("location.country", "de")

    profile = st.session_state[StateKeys.PROFILE]
    assert st.session_state["location.country"] == "Germany"
    assert profile["location"]["country"] == "Germany"

    _update_profile("location.country", "")

    assert "location.country" not in st.session_state
    assert profile["location"]["country"] is None
