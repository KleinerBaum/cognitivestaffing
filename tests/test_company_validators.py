from __future__ import annotations

from typing import Iterator

import pytest
import streamlit as st

from constants.keys import ProfilePaths, StateKeys
from state import ensure_state
from wizard.company_validators import persist_contact_email, persist_primary_city


@pytest.fixture(autouse=True)
def _reset_state() -> Iterator[None]:
    """Ensure every validator test starts from a clean session."""

    st.session_state.clear()
    ensure_state()
    yield
    st.session_state.clear()


def test_persist_contact_email_rejects_empty() -> None:
    """Empty contact emails should clear the profile and raise an error tuple."""

    value, error = persist_contact_email("")
    profile = st.session_state[StateKeys.PROFILE]
    assert value is None
    assert error == (
        "Bitte Kontakt-E-Mail eintragen.",
        "Please enter the contact email.",
    )
    assert profile["company"].get("contact_email") in (None, "")
    assert st.session_state[ProfilePaths.COMPANY_CONTACT_EMAIL] == ""


def test_persist_contact_email_rejects_invalid_format() -> None:
    """Non-email payloads must not persist in the profile."""

    value, error = persist_contact_email("invalid@")
    profile = st.session_state[StateKeys.PROFILE]
    assert value is None
    assert error == (
        "Bitte gültige E-Mail-Adresse verwenden.",
        "Please enter a valid email address.",
    )
    assert profile["company"].get("contact_email") in (None, "")
    assert st.session_state[ProfilePaths.COMPANY_CONTACT_EMAIL] == "invalid@"


def test_persist_contact_email_accepts_valid_payload() -> None:
    """Valid emails are trimmed, stored, and returned without an error."""

    value, error = persist_contact_email(" recruiter@example.com ")
    profile = st.session_state[StateKeys.PROFILE]
    assert value == "recruiter@example.com"
    assert error is None
    assert profile["company"].get("contact_email") == "recruiter@example.com"
    assert st.session_state[ProfilePaths.COMPANY_CONTACT_EMAIL] == "recruiter@example.com"


def test_persist_primary_city_requires_value() -> None:
    """Primary city cannot remain empty because it drives downstream logic."""

    value, error = persist_primary_city("   ")
    profile = st.session_state[StateKeys.PROFILE]
    assert value is None
    assert error == (
        "Bitte primären Standort eintragen.",
        "Please enter the primary city.",
    )
    assert profile["location"].get("primary_city") in (None, "")
    assert st.session_state[ProfilePaths.LOCATION_PRIMARY_CITY] == "   "


def test_persist_primary_city_accepts_trimmed_value() -> None:
    """Valid city values are trimmed and stored back into the profile."""

    value, error = persist_primary_city(" Berlin ")
    profile = st.session_state[StateKeys.PROFILE]
    assert value == "Berlin"
    assert error is None
    assert profile["location"].get("primary_city") == "Berlin"
    assert st.session_state[ProfilePaths.LOCATION_PRIMARY_CITY] == "Berlin"
