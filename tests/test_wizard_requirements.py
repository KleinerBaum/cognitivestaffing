"""Tests for the requirements wizard step."""

from __future__ import annotations

import pytest
import streamlit as st

from constants.keys import StateKeys, UIKeys
from wizard import _render_esco_skill_picker, _step_requirements


class StopWizard(RuntimeError):
    """Sentinel exception to abort the requirements step during tests."""


def test_step_requirements_warns_on_skill_suggestion_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A backend error triggers a localized warning for skill suggestions."""

    st.session_state.clear()
    st.session_state.lang = "de"
    st.session_state.debug = True
    st.session_state[StateKeys.PROFILE] = {
        "requirements": {
            "hard_skills_required": [],
            "hard_skills_optional": [],
            "soft_skills_required": [],
            "soft_skills_optional": [],
            "tools_and_technologies": [],
            "languages_required": [],
            "languages_optional": [],
            "certificates": [],
            "certifications": [],
        },
        "position": {"job_title": "Data Scientist"},
        "compensation": {
            "salary_min": 0,
            "salary_max": 0,
            "salary_provided": False,
            "currency": "EUR",
            "period": "year",
            "benefits": [],
        },
        "company": {"industry": ""},
    }
    st.session_state[StateKeys.SKILL_SUGGESTIONS] = {}

    monkeypatch.setattr("wizard._render_prefilled_preview", lambda *_, **__: None)
    monkeypatch.setattr("wizard.get_missing_critical_fields", lambda *, max_section=None: [])
    monkeypatch.setattr(
        "wizard.get_skill_suggestions", lambda *_args, **_kwargs: ({}, "kaputt")
    )

    monkeypatch.setattr(st, "subheader", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "info", lambda *_, **__: None)

    class FakePanel:
        def __enter__(self) -> "FakePanel":
            return self

        def __exit__(self, *_: object) -> bool:
            return False

        def markdown(self, *_: object, **__: object) -> None:
            return None

        def container(self) -> "FakePanel":
            return FakePanel()

        def columns(self, *args: object, **kwargs: object) -> tuple[object, ...]:
            return st.columns(*args, **kwargs)

    monkeypatch.setattr(st, "container", lambda: FakePanel())

    def fake_tabs(labels: list[str]) -> tuple[FakePanel, FakePanel, FakePanel]:
        return (FakePanel(), FakePanel(), FakePanel())

    monkeypatch.setattr(st, "tabs", fake_tabs)

    captured: dict[str, str] = {}

    def fake_warning(message: str, *_, **__) -> None:
        captured["message"] = message

    def fake_columns(*_, **__) -> tuple[object, ...]:
        raise StopWizard

    monkeypatch.setattr(st, "warning", fake_warning)
    monkeypatch.setattr(st, "columns", fake_columns)

    with pytest.raises(StopWizard):
        _step_requirements()

    assert (
        captured["message"]
        == "Skill-Vorschläge nicht verfügbar (API-Fehler)"
    ), "User-facing warning should be localized"
    assert (
        st.session_state["skill_suggest_error"] == "kaputt"
    ), "Debug information must remain available"


def test_render_esco_skill_picker_adds_skills(monkeypatch: pytest.MonkeyPatch) -> None:
    """Selecting ESCO skills should add them to the required bucket."""

    st.session_state.clear()
    st.session_state.lang = "de"
    st.session_state[StateKeys.ESCO_SKILLS] = ["Data Analysis", "Machine Learning"]
    st.session_state[StateKeys.ESCO_MISSING_SKILLS] = ["Machine Learning"]

    requirements: dict[str, list[str]] = {
        "hard_skills_required": [],
        "hard_skills_optional": [],
    }
    st.session_state[StateKeys.PROFILE] = {"requirements": requirements}

    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    captured_info: dict[str, str] = {}
    monkeypatch.setattr(st, "info", lambda message, *_, **__: captured_info.setdefault("info", message))
    monkeypatch.setattr(st, "success", lambda *_, **__: None)

    def fake_multiselect(label, *, options, default, key):
        assert "ESCO" in label
        assert "Machine Learning" in options
        return ["Machine Learning"]

    monkeypatch.setattr(st, "multiselect", fake_multiselect)

    class DummyColumn:
        def __init__(self, trigger: bool) -> None:
            self._trigger = trigger
            self._calls = 0

        def button(self, *_: object, **__: object) -> bool:
            self._calls += 1
            return self._trigger and self._calls == 1

    monkeypatch.setattr(st, "columns", lambda _: (DummyColumn(True), DummyColumn(False)))

    _render_esco_skill_picker(requirements)

    assert requirements["hard_skills_required"] == ["Machine Learning"]
    assert st.session_state[UIKeys.REQUIREMENTS_ESCO_SKILL_SELECT] == []
    assert "Machine Learning" in captured_info.get("info", "")
