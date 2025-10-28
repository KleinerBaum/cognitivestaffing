"""Tests for synchronising profile updates with session state."""

import streamlit as st

from constants.keys import StateKeys
from state import ensure_state
from wizard import _update_profile


def test_update_profile_syncs_direct_session_state() -> None:
    """Updating the profile should reflect in ``st.session_state``."""

    st.session_state.clear()
    ensure_state()

    _update_profile("company.name", "Acme Robotics")

    assert st.session_state["company.name"] == "Acme Robotics"
    profile = st.session_state[StateKeys.PROFILE]
    assert profile["company"]["name"] == "Acme Robotics"


def test_update_profile_normalizes_phone_in_state() -> None:
    """Phone inputs should be normalised and removable via empty strings."""

    st.session_state.clear()
    ensure_state()

    _update_profile("company.contact_phone", "  +49 (0)30-123 45 67 ext. 9 ")

    profile = st.session_state[StateKeys.PROFILE]
    assert st.session_state["company.contact_phone"] == "+49 30 1234567 ext 9"
    assert profile["company"]["contact_phone"] == "+49 30 1234567 ext 9"

    _update_profile("company.contact_phone", "")

    assert "company.contact_phone" not in st.session_state
    assert profile["company"]["contact_phone"] is None


def test_update_profile_normalizes_website_in_state() -> None:
    """Websites should be coerced to canonical HTTPS URLs and clear to ``None``."""

    st.session_state.clear()
    ensure_state()

    _update_profile("company.website", "example.com/careers ")

    profile = st.session_state[StateKeys.PROFILE]
    assert st.session_state["company.website"] == "https://example.com/careers"
    assert profile["company"]["website"] == "https://example.com/careers"

    _update_profile("company.website", "   ")

    assert "company.website" not in st.session_state
    assert profile["company"]["website"] is None


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
