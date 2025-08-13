"""Tests for critical field validation utilities."""

import streamlit as st

from wizard import FIELD_SECTION_MAP, get_missing_critical_fields


def test_section_filtering() -> None:
    """Fields beyond the inspected section should be ignored."""
    st.session_state.clear()
    st.session_state["position.job_title"] = "Engineer"
    st.session_state["company.name"] = "Acme"
    st.session_state["location.primary_city"] = "Berlin"
    st.session_state["location.country"] = "DE"
    st.session_state["followup_questions"] = []

    assert get_missing_critical_fields(max_section=1) == []
    missing = get_missing_critical_fields(max_section=2)
    assert "position.role_summary" in missing


def test_followup_critical_detection() -> None:
    """Critical follow-up questions count as missing fields."""
    st.session_state.clear()
    for field in FIELD_SECTION_MAP:
        st.session_state[field] = "filled"
    st.session_state["compensation.salary_min"] = ""
    st.session_state["followup_questions"] = [
        {"field": "compensation.salary_min", "priority": "critical"},
        {"field": "compensation.variable_pay", "priority": "normal"},
    ]

    missing = get_missing_critical_fields(
        max_section=FIELD_SECTION_MAP["compensation.salary_min"]
    )
    assert missing == ["compensation.salary_min"]
