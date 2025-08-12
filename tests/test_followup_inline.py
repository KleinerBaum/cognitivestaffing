"""Tests for inline rendering of follow-up questions."""

import streamlit as st

from wizard import render_followups_for


def test_render_followups_updates_state(monkeypatch) -> None:
    """Entering a response should update the corresponding field."""
    st.session_state.clear()
    st.session_state["lang"] = "en"
    st.session_state["followup_questions"] = [
        {"field": "salary", "question": "Salary?"}
    ]

    monkeypatch.setattr(st, "text_input", lambda *a, **k: "100k")
    render_followups_for(["salary"])

    assert st.session_state["salary"] == "100k"
    assert st.session_state["followup_questions"] == []


def test_render_followups_prefill(monkeypatch) -> None:
    """Prefill values should appear as default text."""
    st.session_state.clear()
    st.session_state["lang"] = "en"
    st.session_state["followup_questions"] = [
        {"field": "location", "question": "Location?", "prefill": "Berlin"}
    ]

    def fake_input(label, value="", key=None):
        assert value == "Berlin"
        return value

    monkeypatch.setattr(st, "text_input", fake_input)
    render_followups_for(["location"])

    assert st.session_state["location"] == "Berlin"
    assert st.session_state["followup_questions"] == []
