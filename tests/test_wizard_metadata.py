from __future__ import annotations

from typing import Any

import streamlit as st

from constants.keys import ProfilePaths, StateKeys
from wizard.metadata import get_missing_critical_fields


def _base_profile() -> dict[str, Any]:
    return {
        "company": {"contact_email": ""},
        "location": {"primary_city": ""},
        "meta": {},
    }


def test_get_missing_critical_fields_revalidates_contact_email_widget_state() -> None:
    """Contact email should be treated as missing when the widget holds invalid text."""

    st.session_state.clear()
    profile = _base_profile()
    profile["location"]["primary_city"] = "Berlin"
    st.session_state[StateKeys.PROFILE] = profile
    st.session_state[str(ProfilePaths.COMPANY_CONTACT_EMAIL)] = "invalid@"

    missing = get_missing_critical_fields()

    assert str(ProfilePaths.COMPANY_CONTACT_EMAIL) in missing
    stored_email = st.session_state[StateKeys.PROFILE]["company"].get("contact_email")
    assert stored_email in (None, "")


def test_get_missing_critical_fields_revalidates_primary_city_widget_state() -> None:
    """Primary city should re-run validators when the widget only contains whitespace."""

    st.session_state.clear()
    profile = _base_profile()
    profile["company"]["contact_email"] = "contact@example.com"
    st.session_state[StateKeys.PROFILE] = profile
    st.session_state[str(ProfilePaths.LOCATION_PRIMARY_CITY)] = "   "

    missing = get_missing_critical_fields()

    assert str(ProfilePaths.LOCATION_PRIMARY_CITY) in missing
    stored_city = st.session_state[StateKeys.PROFILE]["location"].get("primary_city")
    assert stored_city in (None, "")
