"""Tests for inline rendering of follow-up questions."""

import streamlit as st

from wizard import render_followups_for


def test_render_followups_updates_state(monkeypatch) -> None:
    """Entering a response should update the corresponding field."""
    st.session_state.clear()
    st.session_state["lang"] = "en"
    st.session_state["followup_questions"] = [
        {"field": "compensation.salary_min", "question": "Salary?"}
    ]

    monkeypatch.setattr(st, "text_input", lambda *a, **k: "100k")
    render_followups_for(["compensation.salary_min"])

    assert st.session_state["compensation.salary_min"] == "100k"
    assert st.session_state["followup_questions"] == []


def test_render_followups_prefill(monkeypatch) -> None:
    """Prefill values should appear as default text."""
    st.session_state.clear()
    st.session_state["lang"] = "en"
    st.session_state["followup_questions"] = [
        {"field": "location.primary_city", "question": "Location?", "prefill": "Berlin"}
    ]

    def fake_input(label, value="", key=None):
        assert value == "Berlin"
        return value

    monkeypatch.setattr(st, "text_input", fake_input)
    render_followups_for(["location.primary_city"])

    assert st.session_state["location.primary_city"] == "Berlin"
    assert st.session_state["followup_questions"] == []


def test_render_followups_critical_prefix(monkeypatch) -> None:
    """Critical questions should be prefixed with a red asterisk."""
    st.session_state.clear()
    st.session_state["lang"] = "en"
    st.session_state["followup_questions"] = [
        {"field": "salary", "question": "Salary?", "priority": "critical"}
    ]

    seen = {"markdown": None, "label": None}

    def fake_markdown(text, **_):
        seen["markdown"] = text

    def fake_input(label, value="", key=None):
        seen["label"] = label
        return "100k"

    monkeypatch.setattr(st, "markdown", fake_markdown)
    monkeypatch.setattr(st, "text_input", fake_input)

    render_followups_for(["salary"])

    assert seen["markdown"] is not None
    assert seen["markdown"].lstrip().startswith("<span style='color:red'>*")
    assert seen["label"] == ""
