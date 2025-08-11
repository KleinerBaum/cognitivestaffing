"""Tests for follow-up question session state handling in wizard."""

import streamlit as st

from wizard import followup_questions_page


def test_followup_questions_skip_blank_field(monkeypatch) -> None:
    """Ensure questions without a field do not write to session state."""
    st.session_state.clear()
    st.session_state["lang"] = "en"
    st.session_state["followup_questions"] = [
        {"field": "", "question": "General note?"},
        {"field": "salary", "question": "Salary?"},
    ]

    def fake_text_input(label: str, value: str = "", key: str | None = None) -> str:
        return "some answer"

    monkeypatch.setattr(st, "text_input", fake_text_input)
    monkeypatch.setattr(st, "header", lambda *a, **k: None)
    monkeypatch.setattr(st, "info", lambda *a, **k: None)

    followup_questions_page()

    assert "" not in st.session_state
    assert st.session_state["salary"] == "some answer"
