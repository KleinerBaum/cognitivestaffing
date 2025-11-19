"""Regression tests for company size extraction and binding."""

from __future__ import annotations

import streamlit as st

from constants.keys import StateKeys
from ingest.heuristics import guess_company_size
from models.need_analysis import NeedAnalysisProfile
from wizard_pages import WIZARD_PAGES
from utils.normalization import extract_company_size, normalize_company_size
from wizard import _extract_company_size, _update_profile


def test_parse_and_bind_size() -> None:
    """Company size should normalise across extractors and UI bindings."""

    text = "Das Team beschäftigt rund 3,370 employees weltweit."

    assert normalize_company_size("rund 3,370 employees") == "3370"
    assert extract_company_size(text) == "3370"
    assert guess_company_size(text) == "3370"
    assert _extract_company_size(text) == "3370"

    st.session_state.clear()
    st.session_state[StateKeys.PROFILE] = NeedAnalysisProfile().model_dump()

    _update_profile("company.size", "3,370 employees")

    assert st.session_state["company.size"] == "3370"
    profile_company = st.session_state[StateKeys.PROFILE]["company"]
    assert profile_company["size"] == "3370"

    company_page = next(page for page in WIZARD_PAGES if page.key == "company")
    assert "company.legal_name" in company_page.summary_fields
