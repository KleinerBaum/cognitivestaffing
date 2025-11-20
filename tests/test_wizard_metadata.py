from __future__ import annotations

from typing import Any

import streamlit as st

from constants.keys import ProfilePaths, StateKeys
from wizard.metadata import filter_followups_by_context, get_missing_critical_fields


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


def test_get_missing_critical_fields_remote_city_not_critical() -> None:
    """Remote roles should not block on missing primary city."""

    st.session_state.clear()
    profile = _base_profile()
    profile["employment"] = {"work_policy": "remote"}
    st.session_state[StateKeys.PROFILE] = profile

    missing = get_missing_critical_fields()

    assert str(ProfilePaths.LOCATION_PRIMARY_CITY) not in missing


def test_filter_followups_by_context_skips_irrelevant_questions() -> None:
    """Context rules should drop travel and management follow-ups when not needed."""

    st.session_state.clear()
    profile: dict[str, Any] = {
        "employment": {"work_policy": "remote", "travel_required": False},
        "position": {"seniority_level": "junior"},
        "location": {"primary_city": ""},
        "meta": {},
    }
    followups = [
        {"field": "location.primary_city", "priority": "critical", "question": "City?"},
        {"field": "employment.travel_share", "priority": "critical", "question": "Travel?"},
        {"field": "position.team_size", "priority": "normal", "question": "Team size?"},
        {"field": "company.name", "priority": "critical", "question": "Company?"},
    ]

    filtered = filter_followups_by_context(followups, profile)
    fields = {entry["field"] for entry in filtered}

    assert "company.name" in fields
    assert "location.primary_city" in fields
    assert "employment.travel_share" not in fields
    assert "position.team_size" not in fields
    for entry in filtered:
        if entry["field"] == "location.primary_city":
            assert entry["priority"] == "optional"


def test_filter_followups_by_context_prioritizes_management_for_senior() -> None:
    """Leadership roles should emphasise reporting line details."""

    st.session_state.clear()
    profile: dict[str, Any] = {
        "employment": {"work_policy": "onsite"},
        "position": {"seniority_level": "Director"},
        "location": {"primary_city": "Berlin"},
        "meta": {},
    }
    followups = [{"field": "position.supervises", "priority": "normal", "question": "How many reports?"}]

    filtered = filter_followups_by_context(followups, profile)

    assert filtered and filtered[0]["priority"] == "critical"
