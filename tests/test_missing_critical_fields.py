"""Tests for critical field validation utilities."""

import streamlit as st

from constants.keys import StateKeys
from ingest.heuristics import apply_basic_fallbacks
from models.need_analysis import NeedAnalysisProfile
from wizard import FIELD_SECTION_MAP, get_missing_critical_fields


def test_section_filtering() -> None:
    """Fields beyond the inspected section should be ignored."""
    st.session_state.clear()
    st.session_state[StateKeys.FOLLOWUPS] = []

    # Section 1 requires company name and the primary country information
    section_one_missing = set(get_missing_critical_fields(max_section=1))
    assert {
        "company.name",
        "company.contact_name",
        "company.contact_email",
        "company.contact_phone",
        "location.primary_city",
        "location.country",
    } <= section_one_missing

    st.session_state["company.name"] = "Acme"
    section_one_missing = set(get_missing_critical_fields(max_section=1))
    assert {
        "company.contact_name",
        "company.contact_email",
        "company.contact_phone",
        "location.primary_city",
        "location.country",
    } <= section_one_missing

    st.session_state["location.primary_city"] = "Berlin"
    missing_after_city = set(get_missing_critical_fields(max_section=1))
    assert missing_after_city == {
        "location.country",
        "company.contact_name",
        "company.contact_email",
        "company.contact_phone",
    }

    st.session_state["company.contact_name"] = "Max"
    st.session_state["company.contact_email"] = "max@example.com"
    st.session_state["company.contact_phone"] = "+49 30 1234567"
    st.session_state["location.country"] = "DE"
    assert get_missing_critical_fields(max_section=1) == []

    # Section 2 requires job title and role summary
    missing = get_missing_critical_fields(max_section=2)
    assert {"position.job_title", "position.role_summary"} <= set(missing)

    st.session_state["position.job_title"] = "Engineer"
    missing = get_missing_critical_fields(max_section=2)
    assert "position.role_summary" in missing

    st.session_state["position.role_summary"] = "Build models"
    assert get_missing_critical_fields(max_section=2) == []


def test_followup_critical_detection() -> None:
    """Critical follow-up questions count as missing fields."""
    st.session_state.clear()
    for field in FIELD_SECTION_MAP:
        st.session_state[field] = "filled"
    st.session_state["compensation.salary_min"] = ""
    st.session_state[StateKeys.FOLLOWUPS] = [
        {"field": "compensation.salary_min", "priority": "critical"},
        {"field": "compensation.variable_pay", "priority": "normal"},
    ]

    missing = get_missing_critical_fields(max_section=99)
    assert missing == ["compensation.salary_min"]


def test_contact_fallback_populates_missing_company_details() -> None:
    """Contact information should be auto-filled when present in the document text."""

    text = """
    Ansprechpartner HR:
    Benjamin Erben (HR Business Partner)
    Telefon 0211/123
    E-Mail: benjamin.erben@rheinbahn.de
    """

    profile = NeedAnalysisProfile()
    updated = apply_basic_fallbacks(profile, text)

    assert updated.company.contact_name == "Benjamin Erben"
    assert updated.company.contact_email == "benjamin.erben@rheinbahn.de"
    assert updated.company.contact_phone == "0211/123"
