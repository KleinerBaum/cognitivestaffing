import streamlit as st
import pytest

from constants.keys import StateKeys
from wizard import (
    FIELD_SECTION_MAP,
    _get_profile_state,
    _render_followup_question,
    _render_followups_for_section,
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

    def fake_input(label, key=None, **kwargs):
        st.session_state[key] = "100k"
        return "100k"

    monkeypatch.setattr(st, "text_input", fake_input)
    monkeypatch.setattr(st, "button", lambda *a, **k: False)
    _render_followup_question(q, data)
    assert data["compensation"]["salary_min"] == "100k"
    assert st.session_state[StateKeys.FOLLOWUPS] == []
    assert data["meta"]["followups_answered"] == ["compensation.salary_min"]
    focus_sentinel = "fu_compensation.salary_min_focus_pending"
    assert focus_sentinel not in st.session_state


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

    def fake_input(label, key=None, **kwargs):
        seen["label"] = label
        st.session_state[key] = "100k"
        return "100k"

    monkeypatch.setattr(st, "markdown", fake_markdown)
    monkeypatch.setattr(st, "toast", lambda *a, **k: None)
    monkeypatch.setattr(st, "text_input", fake_input)
    monkeypatch.setattr(st, "button", lambda *a, **k: False)
    _render_followup_question(q, data)
    assert any(m.lstrip().startswith(":red[*]") for m in seen_markdown)
    assert seen["label"] == "Salary?"
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


def test_followup_focus_runs_once(monkeypatch) -> None:
    """New follow-ups should request focus only on their first render."""

    st.session_state.clear()
    st.session_state["lang"] = "en"
    data: dict = {"meta": {"followups_answered": []}}
    q = {"field": "company.name", "question": "Name?"}
    st.session_state[StateKeys.FOLLOWUPS] = [q]
    seen_scripts: list[str] = []

    def fake_markdown(text, **kwargs):
        if "<script>" in text:
            seen_scripts.append(text)

    call_count = {"value": 0}

    def fake_input(label, key=None, **kwargs):
        call_count["value"] += 1
        focus_key = f"{key}_focus_pending"
        if call_count["value"] == 1:
            assert st.session_state.get(focus_key) is True
        else:
            assert st.session_state.get(focus_key) is False
        return ""

    monkeypatch.setattr(st, "markdown", fake_markdown)
    monkeypatch.setattr(st, "toast", lambda *a, **k: None)
    monkeypatch.setattr(st, "text_input", fake_input)
    monkeypatch.setattr(st, "button", lambda *a, **k: False)

    _render_followup_question(q, data)
    assert any("focus" in script for script in seen_scripts)
    focus_sentinel = "fu_company.name_focus_pending"
    assert st.session_state.get(focus_sentinel) is False

    _render_followup_question(q, data)
    focus_scripts = [script for script in seen_scripts if "focus" in script]
    assert len(focus_scripts) == 1


def test_update_profile_syncs_followup_state() -> None:
    """_update_profile should synchronise follow-up bookkeeping."""

    st.session_state.clear()
    for field in FIELD_SECTION_MAP:
        st.session_state[field] = "filled"

    path = "compensation.salary_min"
    st.session_state[path] = ""
    st.session_state[StateKeys.FOLLOWUPS] = [{"field": path, "priority": "critical"}]
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


@pytest.mark.parametrize(
    ("lang", "expected"),
    (
        ("en", "Contextual suggestions require a configured vector store (VECTOR_STORE_ID)."),
        ("de", "Kontextvorschläge benötigen eine konfigurierte Vector-DB (VECTOR_STORE_ID)."),
    ),
)
def test_followup_section_shows_rag_hint(monkeypatch, lang: str, expected: str) -> None:
    """Sections should surface a hint when RAG suggestions were skipped."""

    st.session_state.clear()
    st.session_state["lang"] = lang
    st.session_state[StateKeys.FOLLOWUPS] = [{"field": "company.name", "question": "Name?"}]
    st.session_state[StateKeys.RAG_CONTEXT_SKIPPED] = True
    seen: list[str] = []

    monkeypatch.setattr(st, "markdown", lambda *_a, **_k: None)
    monkeypatch.setattr(st, "caption", lambda text, **_k: seen.append(text))
    monkeypatch.setattr("wizard._render_followup_question", lambda *_a, **_k: None)

    _render_followups_for_section(("company.",), {})

    assert expected in seen
