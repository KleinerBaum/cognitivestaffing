"""Tests for the requirements wizard step."""

from __future__ import annotations

import pytest
import streamlit as st

from constants.keys import StateKeys
from wizard import _step_requirements


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
