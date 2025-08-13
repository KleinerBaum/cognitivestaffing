"""Tests for critical field validation utilities."""

import streamlit as st

from wizard import FIELD_SECTION_MAP, get_missing_critical_fields


def test_section_filtering() -> None:
    """Fields beyond the inspected section should be ignored."""
    st.session_state.clear()
    st.session_state["job_title"] = "Engineer"
    st.session_state["followup_questions"] = []

    assert get_missing_critical_fields(max_section=1) == []
    missing = get_missing_critical_fields(max_section=2)
    assert "company_name" in missing


def test_followup_critical_detection() -> None:
    """Critical follow-up questions count as missing fields."""
    st.session_state.clear()
    for field in FIELD_SECTION_MAP:
        st.session_state[field] = "filled"
    st.session_state["salary_range"] = ""
    st.session_state["followup_questions"] = [
        {"field": "salary_range", "priority": "critical"},
        {"field": "bonus_compensation", "priority": "normal"},
    ]

    missing = get_missing_critical_fields(max_section=FIELD_SECTION_MAP["salary_range"])
    assert missing == ["salary_range"]
