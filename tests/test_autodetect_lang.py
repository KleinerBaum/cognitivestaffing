"""Tests for automatic language detection."""

import streamlit as st

from wizard import _autodetect_lang


def test_autodetect_lang_switches_to_english() -> None:
    """English text should switch session language to 'en'."""
    st.session_state.clear()
    st.session_state["lang"] = "de"
    _autodetect_lang("We are looking for a Software Engineer")
    assert st.session_state["lang"] == "en"
