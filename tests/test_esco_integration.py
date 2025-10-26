"""Tests for the offline ESCO integration wrapper."""

from __future__ import annotations

import pytest
import streamlit as st

from constants.keys import StateKeys, UIKeys
from integrations import esco


@pytest.fixture(autouse=True)
def _offline_env(monkeypatch):
    monkeypatch.setenv("VACAYSER_OFFLINE", "1")
    yield
    monkeypatch.delenv("VACAYSER_OFFLINE", raising=False)


def test_search_populates_state() -> None:
    """Occupation lookup should populate Streamlit session state."""

    st.session_state.clear()
    result = esco.search_occupation("Software Engineer")
    assert result["group"] == "Information and communications technology professionals"
    assert st.session_state[StateKeys.UI_ESCO_OCCUPATION_OPTIONS]
    assert st.session_state[StateKeys.ESCO_SKILLS]
    assert st.session_state[StateKeys.ESCO_SELECTED_OCCUPATIONS]
    assert st.session_state[UIKeys.POSITION_ESCO_OCCUPATION]
    first_option = st.session_state[StateKeys.UI_ESCO_OCCUPATION_OPTIONS][0]
    assert "preferredLabel" in first_option
    assert st.session_state[StateKeys.ESCO_SKILLS][0]


def test_search_options_returns_candidates() -> None:
    """Occupation options should surface keyword matches."""

    st.session_state.clear()
    options = esco.search_occupation_options("Sales Manager")
    assert options
    assert options[0]["group"]
    assert st.session_state[StateKeys.UI_ESCO_OCCUPATION_OPTIONS] == options
    assert all("preferredLabel" in opt for opt in options)


def test_extraction_snapshot_isolated_from_ui_cache() -> None:
    """UI lookups must not overwrite the extraction snapshot key."""

    st.session_state.clear()
    extraction_snapshot = [{"uri": "urn:example:extraction"}]
    st.session_state[StateKeys.EXTRACTION_ESCO_OCCUPATION_OPTIONS] = list(extraction_snapshot)

    esco.search_occupation_options("Sales Manager")

    assert st.session_state[StateKeys.EXTRACTION_ESCO_OCCUPATION_OPTIONS] == extraction_snapshot
    assert st.session_state[StateKeys.UI_ESCO_OCCUPATION_OPTIONS]
    assert (
        st.session_state[StateKeys.UI_ESCO_OCCUPATION_OPTIONS]
        != st.session_state[StateKeys.EXTRACTION_ESCO_OCCUPATION_OPTIONS]
    )


def test_enrich_skills_uses_cached_data() -> None:
    """Skill enrichment should return deterministic cached data."""

    st.session_state.clear()
    occupation = esco.search_occupation("Nurse")
    skills = esco.enrich_skills(occupation.get("uri", ""))
    assert skills
    assert st.session_state[StateKeys.ESCO_SKILLS] == skills
