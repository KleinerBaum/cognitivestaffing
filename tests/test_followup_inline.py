import streamlit as st

from constants.keys import StateKeys
from wizard import (
    FIELD_SECTION_MAP,
    _get_profile_state,
    _render_followup_question,
    _update_profile,
    get_missing_critical_fields,
)


def test_render_followup_updates_state(monkeypatch) -> None:
    """Entering a response should update the corresponding field."""
    st.session_state.clear()
    st.session_state["lang"] = "en"
    data: dict = {"meta": {"followups_answered": []}}
    q = {"field": "compensation.salary_min", "question": "Salary?"}
    st.session_state[StateKeys.FOLLOWUPS] = [q]
    monkeypatch.setattr(st, "markdown", lambda *a, **k: None)
    monkeypatch.setattr(st, "toast", lambda *a, **k: None)

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
    seen_markdown: list[str] = []
    seen = {"label": None}

    def fake_markdown(text, **_):
        seen_markdown.append(text)

    def fake_input(label, key=None):
        seen["label"] = label
        st.session_state[key] = "100k"
        return "100k"

    monkeypatch.setattr(st, "markdown", fake_markdown)
    monkeypatch.setattr(st, "toast", lambda *a, **k: None)
    monkeypatch.setattr(st, "text_input", fake_input)
    monkeypatch.setattr(st, "button", lambda *a, **k: False)
    _render_followup_question(q, data)
    assert any(m.lstrip().startswith(":red[*]") for m in seen_markdown)
    assert seen["label"] == ""
    assert st.session_state[StateKeys.FOLLOWUPS] == []
    assert data["meta"]["followups_answered"] == ["salary"]


def test_followup_requires_answer(monkeypatch) -> None:
    """Follow-up questions remain until an explicit answer is provided."""
    st.session_state.clear()
    st.session_state["lang"] = "en"
    data: dict = {"meta": {"followups_answered": []}}
    q = {"field": "employment.travel_required", "question": "Travel?"}
    st.session_state[StateKeys.FOLLOWUPS] = [q]
    monkeypatch.setattr(st, "markdown", lambda *a, **k: None)
    monkeypatch.setattr(st, "text_input", lambda *a, **k: "")
    monkeypatch.setattr(st, "toast", lambda *a, **k: None)

    seen_keys: list[str | None] = []

    def fake_button(label, key=None):
        seen_keys.append(key)
        return False

    monkeypatch.setattr(st, "button", fake_button)
    _render_followup_question(q, data)
    assert not any(k and k.endswith("_skip") for k in seen_keys)
    assert st.session_state[StateKeys.FOLLOWUPS] == [q]
    assert data["meta"].get("followups_answered") == []


def test_update_profile_syncs_followup_state() -> None:
    """_update_profile should synchronise follow-up bookkeeping."""

    st.session_state.clear()
    for field in FIELD_SECTION_MAP:
        st.session_state[field] = "filled"

    path = "compensation.salary_min"
    st.session_state[path] = ""
    st.session_state[StateKeys.FOLLOWUPS] = [
        {"field": path, "priority": "critical"}
    ]
    st.session_state[f"fu_{path}"] = ""
    profile = _get_profile_state()
    profile.setdefault("meta", {}).setdefault("followups_answered", [])

    _update_profile(path, "100k")

    assert st.session_state[StateKeys.FOLLOWUPS] == []
    assert f"fu_{path}" not in st.session_state
    answered = profile.get("meta", {}).get("followups_answered", [])
    assert path in answered

    missing = get_missing_critical_fields(max_section=99)
    assert path not in missing

    st.session_state[path] = ""
    _update_profile(path, "")
    answered = profile.get("meta", {}).get("followups_answered", [])
    assert path not in answered
