"""Tests for the requirements wizard step."""

from __future__ import annotations

import pytest
import streamlit as st

from constants.keys import StateKeys
from wizard import _render_skill_board, _step_requirements


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
        raise StopWizard

    monkeypatch.setattr(st, "warning", fake_warning)
    monkeypatch.setattr("wizard.sort_items", lambda items, **_: items)

    with pytest.raises(StopWizard):
        _step_requirements()

    assert (
        captured["message"]
        == "Skill-Vorschläge nicht verfügbar (API-Fehler)"
    ), "User-facing warning should be localized"
    assert (
        st.session_state["skill_suggest_error"] == "kaputt"
    ), "Debug information must remain available"


def test_skill_board_moves_esco_skills(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drag-and-drop board should promote ESCO skills into must-have bucket."""

    st.session_state.clear()
    st.session_state.lang = "de"
    st.session_state[StateKeys.SKILL_SUGGESTION_HINTS] = []
    st.session_state[StateKeys.SKILL_BOARD_STATE] = {}
    st.session_state[StateKeys.SKILL_BOARD_META] = {}

    requirements: dict[str, list[str]] = {
        "hard_skills_required": [],
        "hard_skills_optional": [],
        "soft_skills_required": [],
        "soft_skills_optional": [],
    }

    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "info", lambda *_, **__: None)

    class DummyContainer:
        def __enter__(self) -> "DummyContainer":
            return self

        def __exit__(self, *_: object) -> None:
            return None

    monkeypatch.setattr(st, "container", lambda: DummyContainer())

    def fake_sort_items(items, **_kwargs):
        updated = []
        for container in items:
            header = container.get("header")
            if isinstance(header, str) and (
                "Muss" in header or "Must" in header
            ):
                updated.append(
                    {"header": header, "items": ["Machine Learning ⟮ESCO⟯"]}
                )
            elif isinstance(header, str) and "ESCO" in header:
                updated.append({"header": header, "items": []})
            else:
                updated.append(container)
        return updated

    monkeypatch.setattr("wizard.sort_items", fake_sort_items)

    _render_skill_board(
        requirements,
        llm_suggestions={},
        esco_skills=["Machine Learning", "Data Analysis"],
        missing_esco_skills=["Machine Learning"],
    )

    assert requirements["hard_skills_required"] == ["Machine Learning"]
    assert st.session_state[StateKeys.SKILL_BUCKETS]["must"] == ["Machine Learning"]
