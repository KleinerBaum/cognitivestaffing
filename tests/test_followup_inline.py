import streamlit as st

from constants.keys import StateKeys
from wizard import _render_followup_question


def test_render_followup_updates_state(monkeypatch) -> None:
    """Entering a response should update the corresponding field."""
    st.session_state.clear()
    st.session_state["lang"] = "en"
    data: dict = {}
    q = {"field": "compensation.salary_min", "question": "Salary?"}
    st.session_state[StateKeys.FOLLOWUPS] = [q]
    monkeypatch.setattr(st, "markdown", lambda *a, **k: None)

    def fake_input(label, key=None):
        st.session_state[key] = "100k"
        return "100k"

    monkeypatch.setattr(st, "text_input", fake_input)
    _render_followup_question(q, data)
    assert data["compensation"]["salary_min"] == "100k"
    assert st.session_state[StateKeys.FOLLOWUPS] == []


def test_render_followups_critical_prefix(monkeypatch) -> None:
    """Critical questions should be prefixed with a red asterisk."""
    st.session_state.clear()
    st.session_state["lang"] = "en"
    data: dict = {}
    q = {"field": "salary", "question": "Salary?", "priority": "critical"}
    st.session_state[StateKeys.FOLLOWUPS] = [q]
    seen = {"markdown": None, "label": None}

    def fake_markdown(text, **_):
        seen["markdown"] = text

    def fake_input(label, key=None):
        seen["label"] = label
        st.session_state[key] = "100k"
        return "100k"

    monkeypatch.setattr(st, "markdown", fake_markdown)
    monkeypatch.setattr(st, "text_input", fake_input)
    _render_followup_question(q, data)
    assert seen["markdown"] is not None
    assert seen["markdown"].lstrip().startswith("<span style='color:red'>*")
    assert seen["label"] == ""
    assert st.session_state[StateKeys.FOLLOWUPS] == []
