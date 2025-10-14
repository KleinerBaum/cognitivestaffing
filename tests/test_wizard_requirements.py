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
    monkeypatch.setattr("wizard.get_skill_suggestions", lambda *_args, **_kwargs: ({}, "kaputt"))

    monkeypatch.setattr(st, "subheader", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "warning", lambda *_, **__: None)

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

    assert captured["message"] == "Skill-Vorschläge nicht verfügbar (API-Fehler)", (
        "User-facing warning should be localized"
    )
    assert st.session_state["skill_suggest_error"] == "kaputt", "Debug information must remain available"


def test_step_requirements_initializes_requirements(monkeypatch: pytest.MonkeyPatch) -> None:
    """The requirements step should populate an empty requirements block."""

    st.session_state.clear()
    st.session_state.lang = "de"
    st.session_state[StateKeys.SKILL_SUGGESTION_HINTS] = []
    st.session_state[StateKeys.SKILL_SUGGESTIONS] = {}
    st.session_state[StateKeys.SKILL_BOARD_STATE] = {}
    st.session_state[StateKeys.SKILL_BOARD_META] = {}
    st.session_state[StateKeys.PROFILE] = {
        "position": {"job_title": "Data Scientist"},
        "company": {},
    }

    monkeypatch.setattr("wizard._render_prefilled_preview", lambda *_, **__: None)
    monkeypatch.setattr("wizard.get_missing_critical_fields", lambda *, max_section=None: [])
    monkeypatch.setattr("wizard.get_skill_suggestions", lambda *_args, **_kwargs: ({}, None))
    monkeypatch.setattr("wizard._chip_multiselect", lambda *_, **__: [])

    class FakePanel:
        def __enter__(self) -> "FakePanel":
            return self

        def __exit__(self, *_: object) -> bool:
            return False

        def markdown(self, *_: object, **__: object) -> None:
            return None

        def container(self) -> "FakePanel":
            return FakePanel()

    def fake_columns(spec, **_: object) -> tuple[FakePanel, ...]:
        count = spec if isinstance(spec, int) else len(spec)
        return tuple(FakePanel() for _ in range(count))

    def fake_text_area(*_: object, **kwargs: object) -> str:
        key = kwargs.get("key")
        value_provided = "value" in kwargs
        if value_provided:
            result = kwargs["value"]
        else:
            existing = st.session_state.get(key) if isinstance(key, str) else ""
            result = existing if isinstance(existing, str) else ""
        if isinstance(key, str):
            st.session_state[key] = result
        return str(result)

    monkeypatch.setattr(st, "container", lambda: FakePanel())
    monkeypatch.setattr(st, "columns", fake_columns)
    monkeypatch.setattr(st, "text_area", fake_text_area)
    monkeypatch.setattr(st, "subheader", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "info", lambda *_, **__: None)
    monkeypatch.setattr(st, "warning", lambda *_, **__: None)

    captured: dict[str, dict[str, list[str]]] = {}

    def fake_skill_board(requirements: dict[str, list[str]], **_: object) -> None:
        captured["requirements"] = requirements
        requirements["hard_skills_required"] = ["Python"]
        raise StopWizard

    monkeypatch.setattr("wizard._render_skill_board", fake_skill_board)

    with pytest.raises(StopWizard):
        _step_requirements()

    profile = st.session_state[StateKeys.PROFILE]
    assert "requirements" in profile, "requirements section should be initialised"
    assert profile["requirements"]["hard_skills_required"] == ["Python"]
    assert captured["requirements"] is profile["requirements"], "skill board must receive the live requirements dict"


def test_responsibilities_seed_preserves_user_input(monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing responsibilities stay visible and accept edits without warnings."""

    st.session_state.clear()
    st.session_state.lang = "de"
    st.session_state[StateKeys.SKILL_SUGGESTION_HINTS] = []
    st.session_state[StateKeys.SKILL_SUGGESTIONS] = {}
    st.session_state[StateKeys.SKILL_BOARD_STATE] = {}
    st.session_state[StateKeys.SKILL_BOARD_META] = {}
    st.session_state[StateKeys.PROFILE] = {
        "position": {"job_title": "Data Scientist"},
        "company": {},
        "responsibilities": {"items": ["Initial scope alignment"]},
    }

    monkeypatch.setattr("wizard._render_prefilled_preview", lambda *_, **__: None)
    monkeypatch.setattr("wizard.get_missing_critical_fields", lambda *, max_section=None: [])
    monkeypatch.setattr("wizard.get_skill_suggestions", lambda *_args, **_kwargs: ({}, None))
    monkeypatch.setattr("wizard._chip_multiselect", lambda *_, **__: [])

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

    def fake_columns(spec, **_: object) -> tuple[FakePanel, ...]:
        count = spec if isinstance(spec, int) else len(spec)
        return tuple(FakePanel() for _ in range(count))

    responsibilities_key = "ui.requirements.responsibilities"
    responsibilities_seed_key = f"{responsibilities_key}.__seed"
    user_inputs = ["- Updated KPI ownership", None]
    call_history: list[dict[str, object]] = []

    def fake_text_area(*_: object, **kwargs: object) -> str:
        key = kwargs.get("key")
        value_provided = "value" in kwargs
        existing_before = isinstance(key, str) and key in st.session_state
        if value_provided and existing_before:
            raise AssertionError("value argument should be omitted when the widget key already exists")
        call_index = len(call_history)
        preferred = user_inputs[call_index] if call_index < len(user_inputs) else None
        if preferred is not None:
            result = preferred
        elif value_provided:
            result = kwargs["value"]
        else:
            existing_value = st.session_state.get(key) if isinstance(key, str) else ""
            result = existing_value if isinstance(existing_value, str) else ""
        if isinstance(key, str):
            st.session_state[key] = result
        call_history.append(
            {
                "value_provided": value_provided,
                "value_argument": kwargs.get("value"),
                "result": result,
            }
        )
        return str(result)

    def fake_skill_board(requirements: dict[str, list[str]], **_: object) -> None:
        raise StopWizard

    monkeypatch.setattr(st, "container", lambda: FakePanel())
    monkeypatch.setattr(st, "columns", fake_columns)
    monkeypatch.setattr(st, "text_area", fake_text_area)
    monkeypatch.setattr(st, "subheader", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "info", lambda *_, **__: None)
    monkeypatch.setattr(st, "warning", lambda *_, **__: None)
    monkeypatch.setattr(st, "tabs", lambda labels: tuple(FakePanel() for _ in labels))
    monkeypatch.setattr(st, "button", lambda *_, **__: False)
    monkeypatch.setattr("wizard._render_skill_board", fake_skill_board)

    with pytest.raises(StopWizard):
        _step_requirements()

    data = st.session_state[StateKeys.PROFILE]
    assert data["responsibilities"]["items"] == [
        "Updated KPI ownership"
    ], "Sanitized responsibilities should persist in the profile"
    assert (
        st.session_state[responsibilities_seed_key] == "Updated KPI ownership"
    ), "Seed value should track the stored responsibilities"
    assert call_history[0]["value_provided"] is True
    assert call_history[0]["value_argument"] == "Initial scope alignment"

    with pytest.raises(StopWizard):
        _step_requirements()

    assert call_history[1]["value_provided"] is False
    assert call_history[1]["result"] == "- Updated KPI ownership"
    assert (
        st.session_state[responsibilities_key] == "- Updated KPI ownership"
    ), "Raw session state should keep the user edit between renders"
    assert (
        st.session_state[responsibilities_seed_key] == "Updated KPI ownership"
    ), "Seed value should remain the sanitized join"


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
            if isinstance(header, str) and ("Muss" in header or "Must" in header):
                updated.append({"header": header, "items": ["Machine Learning ⟮ESCO⟯"]})
            elif isinstance(header, str) and ("Vorsch" in header or "suggest" in header.lower()):
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
    assert st.session_state[StateKeys.ESCO_MISSING_SKILLS] == []
