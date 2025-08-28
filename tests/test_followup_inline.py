import streamlit as st

from constants.keys import StateKeys
from wizard import _render_followup_question


def test_render_followup_updates_state(monkeypatch) -> None:
    """Entering a response should update the corresponding field."""
    st.session_state.clear()
    st.session_state["lang"] = "en"
    data: dict = {"meta": {"followups_answered": []}}
    q = {"field": "compensation.salary_min", "question": "Salary?"}
    st.session_state[StateKeys.FOLLOWUPS] = [q]
    monkeypatch.setattr(st, "markdown", lambda *a, **k: None)

    def fake_input(label, key=None):
        st.session_state[key] = "100k"
        return "100k"

    monkeypatch.setattr(st, "text_input", fake_input)
    monkeypatch.setattr(st, "button", lambda *a, **k: False)
    _render_followup_question(q, data)
    assert data["compensation"]["salary_min"] == "100k"
    assert st.session_state[StateKeys.FOLLOWUPS] == []
    assert data["meta"]["followups_answered"] == ["compensation.salary_min"]


def test_render_followups_critical_prefix(monkeypatch) -> None:
    """Critical questions should be prefixed with a red asterisk."""
    st.session_state.clear()
    st.session_state["lang"] = "en"
    data: dict = {"meta": {"followups_answered": []}}
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
    monkeypatch.setattr(st, "button", lambda *a, **k: False)
    _render_followup_question(q, data)
    assert seen["markdown"] is not None
    assert seen["markdown"].lstrip().startswith("<span style='color:red'>*")
    assert seen["label"] == ""
    assert st.session_state[StateKeys.FOLLOWUPS] == []
    assert data["meta"]["followups_answered"] == ["salary"]


def test_skip_followup(monkeypatch) -> None:
    """Skipping a question should mark it as completed without storing a value."""
    st.session_state.clear()
    st.session_state["lang"] = "en"
    data: dict = {"meta": {"followups_answered": []}}
    q = {"field": "employment.travel_required", "question": "Travel?"}
    st.session_state[StateKeys.FOLLOWUPS] = [q]
    monkeypatch.setattr(st, "markdown", lambda *a, **k: None)
    monkeypatch.setattr(st, "text_input", lambda *a, **k: "")

    def fake_button(label, key=None):
        return key.endswith("_skip")

    monkeypatch.setattr(st, "button", fake_button)
    _render_followup_question(q, data)
    assert st.session_state[StateKeys.FOLLOWUPS] == []
    assert data["meta"]["followups_answered"] == ["employment.travel_required"]
    assert "employment" not in data
