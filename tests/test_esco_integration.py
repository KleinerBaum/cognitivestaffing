"""Tests for the offline ESCO integration wrapper."""

import streamlit as st

from constants.keys import StateKeys
from integrations import esco


def test_search_populates_state() -> None:
    """Occupation lookup should populate Streamlit session state."""

    st.session_state.clear()
    result = esco.search_occupation("Software Engineer")
    assert result["group"] == "Information and communications technology professionals"
    assert st.session_state[StateKeys.ESCO_OCCUPATION_OPTIONS]
    assert st.session_state[StateKeys.ESCO_SKILLS]


def test_search_options_returns_candidates() -> None:
    """Occupation options should surface keyword matches."""

    st.session_state.clear()
    options = esco.search_occupation_options("Sales Manager")
    assert options
    assert options[0]["group"]
    assert st.session_state[StateKeys.ESCO_OCCUPATION_OPTIONS] == options


def test_enrich_skills_uses_cached_data() -> None:
    """Skill enrichment should return deterministic cached data."""

    st.session_state.clear()
    occupation = esco.search_occupation("Nurse")
    skills = esco.enrich_skills(occupation.get("uri", ""))
    assert skills
    assert st.session_state[StateKeys.ESCO_SKILLS] == skills
