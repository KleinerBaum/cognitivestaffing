"""Tests for the requirements wizard step."""

from __future__ import annotations

from contextlib import contextmanager

import pytest
import streamlit as st

from constants.keys import StateKeys, UIKeys
from wizard import _render_skill_board, _skill_board_labels, _step_requirements


def _fake_panel_text_input(*_: object, key: object | None = None, value: object | None = None, **__: object) -> str:
    """Mimic ``st.text_input`` enough for wizard tests."""

    if isinstance(key, str) and key in st.session_state and value is None:
        existing = st.session_state[key]
        result = existing if isinstance(existing, str) else ""
    elif value is None:
        result = ""
    else:
        result = str(value)

    if isinstance(key, str):
        st.session_state[key] = result

    return result


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
    st.session_state[StateKeys.REQUIREMENTS_ESCO_OPT_IN] = True

    monkeypatch.setattr("wizard._render_prefilled_preview", lambda *_, **__: None)
    monkeypatch.setattr("wizard.get_missing_critical_fields", lambda *, max_section=None: [])
    monkeypatch.setattr("wizard.get_skill_suggestions", lambda *_args, **_kwargs: ({}, "kaputt"))

    monkeypatch.setattr(st, "subheader", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "warning", lambda *_, **__: None)
    monkeypatch.setattr(st, "text_input", lambda *_, **__: "")

    def fake_button(*_args: object, **kwargs: object) -> bool:
        return kwargs.get("key") == UIKeys.REQUIREMENTS_FETCH_AI_SUGGESTIONS

    @contextmanager
    def fake_spinner(*_args: object, **_kwargs: object) -> None:
        yield

    monkeypatch.setattr(st, "spinner", fake_spinner)
    monkeypatch.setattr(st, "button", fake_button)

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

        def text_input(self, *args: object, **kwargs: object) -> str:
            return _fake_panel_text_input(*args, **kwargs)

        def button(self, *args: object, **kwargs: object) -> bool:
            return bool(st.button(*args, **kwargs))

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
    st.session_state[StateKeys.REQUIREMENTS_ESCO_OPT_IN] = True
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

        def text_input(self, *args: object, **kwargs: object) -> str:
            return _fake_panel_text_input(*args, **kwargs)

        def button(self, *args: object, **kwargs: object) -> bool:
            return bool(st.button(*args, **kwargs))

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
    monkeypatch.setattr(st, "text_input", lambda *_, **__: "")

    triggered = {"ai": False}

    def fake_button(*_args: object, **kwargs: object) -> bool:
        key = kwargs.get("key")
        if key == UIKeys.REQUIREMENTS_FETCH_AI_SUGGESTIONS and not triggered["ai"]:
            triggered["ai"] = True
            return True
        return False

    @contextmanager
    def fake_spinner(*_args: object, **_kwargs: object) -> None:
        yield

    monkeypatch.setattr(st, "spinner", fake_spinner)
    monkeypatch.setattr(st, "button", fake_button)

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
    st.session_state[StateKeys.REQUIREMENTS_ESCO_OPT_IN] = True
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

        def text_input(self, *args: object, **kwargs: object) -> str:
            return _fake_panel_text_input(*args, **kwargs)

        def button(self, *args: object, **kwargs: object) -> bool:
            return bool(st.button(*args, **kwargs))

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
    monkeypatch.setattr(st, "text_input", lambda *_, **__: "")
    monkeypatch.setattr(st, "button", lambda *_, **__: False)
    monkeypatch.setattr(st, "tabs", lambda labels: tuple(FakePanel() for _ in labels))
    monkeypatch.setattr("wizard._render_skill_board", fake_skill_board)

    with pytest.raises(StopWizard):
        _step_requirements()

    data = st.session_state[StateKeys.PROFILE]
    assert data["responsibilities"]["items"] == ["Updated KPI ownership"], (
        "Sanitized responsibilities should persist in the profile"
    )
    assert st.session_state[responsibilities_seed_key] == "Updated KPI ownership", (
        "Seed value should track the stored responsibilities"
    )
    assert call_history[0]["value_provided"] is True
    assert call_history[0]["value_argument"] == "Initial scope alignment"

    with pytest.raises(StopWizard):
        _step_requirements()

    assert call_history[1]["value_provided"] is False
    assert call_history[1]["result"] == "- Updated KPI ownership"
    assert st.session_state[responsibilities_key] == "- Updated KPI ownership", (
        "Raw session state should keep the user edit between renders"
    )
    assert st.session_state[responsibilities_seed_key] == "Updated KPI ownership", (
        "Seed value should remain the sanitized join"
    )


def test_skill_suggestions_wait_for_user_trigger(monkeypatch: pytest.MonkeyPatch) -> None:
    """AI suggestions should only fetch after the user clicks the trigger button."""

    st.session_state.clear()
    st.session_state.lang = "de"
    st.session_state[StateKeys.PROFILE] = {
        "position": {"job_title": "Data Scientist"},
        "company": {},
    }
    st.session_state[StateKeys.SKILL_SUGGESTION_HINTS] = []
    st.session_state[StateKeys.SKILL_SUGGESTIONS] = {}
    st.session_state[StateKeys.SKILL_BOARD_STATE] = {}
    st.session_state[StateKeys.SKILL_BOARD_META] = {}
    st.session_state[StateKeys.ESCO_SKILLS] = ["ESCO Analytics"]
    st.session_state[StateKeys.ESCO_MISSING_SKILLS] = ["Missing insight"]
    st.session_state[StateKeys.REQUIREMENTS_ESCO_OPT_IN] = False

    monkeypatch.setattr("wizard._render_prefilled_preview", lambda *_, **__: None)
    monkeypatch.setattr("wizard.get_missing_critical_fields", lambda *, max_section=None: [])

    calls: list[str] = []

    def fake_get_skill_suggestions(*_args: object, **_kwargs: object) -> tuple[dict[str, dict[str, list[str]]], None]:
        calls.append("called")
        return {"hard_skills": {"core": ["Python"]}}, None

    monkeypatch.setattr("wizard.get_skill_suggestions", fake_get_skill_suggestions)

    class FakePanel:
        def __enter__(self) -> "FakePanel":
            return self

        def __exit__(self, *_: object) -> bool:
            return False

        def markdown(self, *_: object, **__: object) -> None:
            return None

        def container(self) -> "FakePanel":
            return FakePanel()

        def text_input(self, *args: object, **kwargs: object) -> str:
            return _fake_panel_text_input(*args, **kwargs)

        def button(self, *args: object, **kwargs: object) -> bool:
            return bool(st.button(*args, **kwargs))

    def fake_columns(spec: object, **_: object) -> tuple[FakePanel, ...]:
        count = spec if isinstance(spec, int) else len(spec)
        return tuple(FakePanel() for _ in range(int(count)))

    def fake_text_area(*_: object, **kwargs: object) -> str:
        key = kwargs.get("key")
        value = kwargs.get("value", "")
        if isinstance(key, str):
            st.session_state[key] = value
        return str(value)

    monkeypatch.setattr(st, "container", lambda: FakePanel())
    monkeypatch.setattr(st, "columns", fake_columns)
    monkeypatch.setattr(st, "text_area", fake_text_area)
    monkeypatch.setattr(st, "header", lambda *_, **__: None)
    monkeypatch.setattr(st, "subheader", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "info", lambda *_, **__: None)
    monkeypatch.setattr(st, "warning", lambda *_, **__: None)
    monkeypatch.setattr(st, "text_input", lambda *_, **__: "")
    monkeypatch.setattr(st, "button", lambda *_, **__: False)

    original_skill_board = _render_skill_board

    def wrapped_skill_board(*args: object, **kwargs: object) -> None:
        original_skill_board(*args, **kwargs)
        raise StopWizard

    monkeypatch.setattr("wizard.sort_items", lambda items, **_: items)
    monkeypatch.setattr("wizard._render_skill_board", wrapped_skill_board)

    with pytest.raises(StopWizard):
        _step_requirements()

    assert calls == [], "AI suggestions must not fetch before the button is clicked"
    board_state = st.session_state.get(StateKeys.SKILL_BOARD_STATE, {}) or {}
    assert board_state.get("source_ai") == [], "No AI suggestions should populate the board before the trigger"
    assert board_state.get("source_esco") == [], "ESCO bucket should remain empty before opt-in"
    assert st.session_state[StateKeys.REQUIREMENTS_ESCO_OPT_IN] is False


def test_skill_suggestions_fetches_on_button(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clicking the AI button fetches suggestions and surfaces them on the board."""

    st.session_state.clear()
    st.session_state.lang = "de"
    st.session_state[StateKeys.PROFILE] = {
        "position": {"job_title": "Data Scientist"},
        "company": {},
    }
    st.session_state[StateKeys.SKILL_SUGGESTION_HINTS] = []
    st.session_state[StateKeys.SKILL_SUGGESTIONS] = {}
    st.session_state[StateKeys.SKILL_BOARD_STATE] = {}
    st.session_state[StateKeys.SKILL_BOARD_META] = {}
    st.session_state[StateKeys.ESCO_SKILLS] = ["ESCO Analytics"]
    st.session_state[StateKeys.ESCO_MISSING_SKILLS] = []
    st.session_state[StateKeys.REQUIREMENTS_ESCO_OPT_IN] = True

    monkeypatch.setattr("wizard._render_prefilled_preview", lambda *_, **__: None)
    monkeypatch.setattr("wizard.get_missing_critical_fields", lambda *, max_section=None: [])

    calls: list[str] = []

    def fake_get_skill_suggestions(*_args: object, **_kwargs: object) -> tuple[dict[str, dict[str, list[str]]], None]:
        calls.append("called")
        return {"hard_skills": {"core": ["Python"]}}, None

    monkeypatch.setattr("wizard.get_skill_suggestions", fake_get_skill_suggestions)

    class FakePanel:
        def __enter__(self) -> "FakePanel":
            return self

        def __exit__(self, *_: object) -> bool:
            return False

        def markdown(self, *_: object, **__: object) -> None:
            return None

        def container(self) -> "FakePanel":
            return FakePanel()

        def text_input(self, *args: object, **kwargs: object) -> str:
            return _fake_panel_text_input(*args, **kwargs)

        def button(self, *args: object, **kwargs: object) -> bool:
            return bool(st.button(*args, **kwargs))

    def fake_columns(spec: object, **_: object) -> tuple[FakePanel, ...]:
        count = spec if isinstance(spec, int) else len(spec)
        return tuple(FakePanel() for _ in range(int(count)))

    def fake_text_area(*_: object, **kwargs: object) -> str:
        key = kwargs.get("key")
        value = kwargs.get("value", "")
        if isinstance(key, str):
            st.session_state[key] = value
        return str(value)

    monkeypatch.setattr(st, "container", lambda: FakePanel())
    monkeypatch.setattr(st, "columns", fake_columns)
    monkeypatch.setattr(st, "text_area", fake_text_area)
    monkeypatch.setattr(st, "subheader", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "info", lambda *_, **__: None)
    monkeypatch.setattr(st, "warning", lambda *_, **__: None)

    triggered = {"ai": False}

    def fake_button(*_args: object, **kwargs: object) -> bool:
        key = kwargs.get("key")
        if key == UIKeys.REQUIREMENTS_FETCH_AI_SUGGESTIONS and not triggered["ai"]:
            triggered["ai"] = True
            return True
        return False

    monkeypatch.setattr(st, "button", fake_button)

    captured: dict[str, object] = {}

    def fake_skill_board(
        requirements: dict[str, list[str]],
        *,
        llm_suggestions: dict[str, dict[str, list[str]]],
        esco_skills: list[str],
        **_: object,
    ) -> None:
        captured["llm"] = llm_suggestions
        captured["esco"] = esco_skills
        raise StopWizard

    monkeypatch.setattr("wizard._render_skill_board", fake_skill_board)

    with pytest.raises(StopWizard):
        _step_requirements()

    assert calls == ["called"], "AI suggestions should be fetched after the button is clicked"
    assert captured["llm"] == {"hard_skills": {"core": ["Python"]}}
    assert captured["esco"] == ["ESCO Analytics"], "ESCO suggestions should surface after opt-in"


def test_skill_suggestions_refresh_clears_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refreshing AI suggestions should clear cached results."""

    st.session_state.clear()
    st.session_state.lang = "de"
    st.session_state[StateKeys.PROFILE] = {
        "position": {"job_title": "Data Scientist"},
        "company": {},
    }
    st.session_state[StateKeys.SKILL_SUGGESTION_HINTS] = []
    st.session_state[StateKeys.SKILL_SUGGESTIONS] = {
        "_title": "Data Scientist",
        "_lang": "de",
        "hard_skills": {"llm": ["Python"]},
    }
    st.session_state[StateKeys.REQUIREMENTS_ESCO_OPT_IN] = True

    monkeypatch.setattr("wizard._render_prefilled_preview", lambda *_, **__: None)
    monkeypatch.setattr("wizard.get_missing_critical_fields", lambda *, max_section=None: [])
    monkeypatch.setattr(
        "wizard.get_skill_suggestions",
        lambda *_args, **_kwargs: ({"hard_skills": {"core": ["Python"]}}, None),
    )
    monkeypatch.setattr("wizard._render_skill_board", lambda *_, **__: None)

    class FakePanel:
        def __enter__(self) -> "FakePanel":
            return self

        def __exit__(self, *_: object) -> bool:
            return False

        def markdown(self, *_: object, **__: object) -> None:
            return None

        def container(self) -> "FakePanel":
            return FakePanel()

        def text_input(self, *args: object, **kwargs: object) -> str:
            return _fake_panel_text_input(*args, **kwargs)

        def button(self, *args: object, **kwargs: object) -> bool:
            return bool(st.button(*args, **kwargs))

    def fake_columns(spec: object, **_: object) -> tuple[FakePanel, ...]:
        count = spec if isinstance(spec, int) else len(spec)
        return tuple(FakePanel() for _ in range(int(count)))

    def fake_text_area(*_: object, **kwargs: object) -> str:
        key = kwargs.get("key")
        if isinstance(key, str):
            st.session_state[key] = kwargs.get("value", "")
        return str(kwargs.get("value", ""))

    monkeypatch.setattr(st, "container", lambda: FakePanel())
    monkeypatch.setattr(st, "columns", fake_columns)
    monkeypatch.setattr(st, "text_area", fake_text_area)
    monkeypatch.setattr(st, "subheader", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "info", lambda *_, **__: None)
    monkeypatch.setattr(st, "warning", lambda *_, **__: None)
    monkeypatch.setattr(st, "text_input", lambda *_, **__: "")

    triggered = {"refresh": False}

    def fake_button(*_args: object, **kwargs: object) -> bool:
        key = kwargs.get("key")
        if key == "ai_suggestions.hard_skills_required.must.refresh" and not triggered["refresh"]:
            triggered["refresh"] = True
            return True
        return False

    monkeypatch.setattr(st, "button", fake_button)

    def fake_rerun() -> None:
        raise StopWizard

    monkeypatch.setattr(st, "rerun", fake_rerun)

    with pytest.raises(StopWizard):
        _step_requirements()

    assert StateKeys.SKILL_SUGGESTIONS not in st.session_state, "Refresh should remove cached suggestions"


def test_skill_board_moves_esco_skills(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drag-and-drop board should promote ESCO skills into must-have bucket."""

    st.session_state.clear()
    st.session_state.lang = "de"
    st.session_state[StateKeys.SKILL_SUGGESTION_HINTS] = []
    st.session_state[StateKeys.SKILL_BOARD_STATE] = {}
    st.session_state[StateKeys.SKILL_BOARD_META] = {}
    st.session_state[StateKeys.REQUIREMENTS_ESCO_OPT_IN] = True

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

    labels = _skill_board_labels("de")
    must_header = labels["target_must"]
    esco_header = labels["source_esco"]

    captured_payload: list[list[dict[str, object]]] = []

    def fake_sort_items(items, **_kwargs):
        captured_payload.append(items)
        updated = []
        esco_chip = None
        for container in items:
            header = container.get("header")
            if isinstance(header, str) and header == esco_header:
                esco_items = list(container.get("items", []) or [])
                if esco_items:
                    for candidate in esco_items:
                        if isinstance(candidate, str) and "Machine Learning" in candidate:
                            esco_chip = candidate
                            break
                    if esco_chip is None:
                        esco_chip = esco_items[0]
                updated.append({"header": header, "items": []})
            elif isinstance(header, str) and header == must_header:
                moved_items = list(container.get("items", []) or [])
                if esco_chip is not None:
                    moved_items.append(esco_chip)
                updated.append({"header": header, "items": moved_items})
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

    board_state = st.session_state[StateKeys.SKILL_BOARD_STATE]
    meta = st.session_state[StateKeys.SKILL_BOARD_META]
    assert captured_payload, "sort_items should receive a payload"
    first_payload = captured_payload[0]
    esco_container = next(container for container in first_payload if container.get("header") == esco_header)
    esco_items_markup = esco_container.get("items", []) or []
    assert esco_items_markup, "ESCO container should start with items"
    moved_labels = [meta[item]["label"] for item in board_state["target_must"] if item in meta]
    assert moved_labels == ["Machine Learning"], moved_labels
    if board_state["target_must"]:
        first_identifier = board_state["target_must"][0]
        assert meta[first_identifier]["category"] == "hard"
    assert requirements["hard_skills_required"] == ["Machine Learning"]
    assert st.session_state[StateKeys.SKILL_BUCKETS]["must"] == ["Machine Learning"]
    assert st.session_state[StateKeys.ESCO_MISSING_SKILLS] == []


def test_skill_board_rehydrates_legacy_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Legacy board payloads are normalised into current structure."""

    st.session_state.clear()
    st.session_state.lang = "de"
    st.session_state[StateKeys.SKILL_BOARD_STATE] = {
        "target_must": ["Python ⟮Auto⟯", "Python ⟮Auto⟯", "Teamwork ⟮KI⟯"],
        "target_nice": ["Storytelling ⟮KI⟯"],
        "source_auto": ["Communication ⟮ESCO⟯"],
    }
    st.session_state[StateKeys.SKILL_BOARD_META] = {
        "Python ⟮Auto⟯": {"label": "Python", "category": "hard", "source": "auto"},
        "Teamwork ⟮KI⟯": {"label": "Teamwork", "category": "soft", "source": "ai"},
        "Storytelling ⟮KI⟯": {"label": "Storytelling", "category": "soft", "source": "ai"},
        "Communication ⟮ESCO⟯": {
            "label": "Communication",
            "category": "soft",
            "source": "esco",
        },
    }

    requirements: dict[str, list[str]] = {
        "hard_skills_required": [],
        "hard_skills_optional": [],
        "soft_skills_required": [],
        "soft_skills_optional": [],
    }

    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "header", lambda *_, **__: None)
    monkeypatch.setattr(st, "subheader", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "warning", lambda *_, **__: None)
    monkeypatch.setattr("wizard.sort_items", lambda items, **_: items)

    _render_skill_board(
        requirements,
        llm_suggestions={},
        esco_skills=["Communication"],
        missing_esco_skills=["Communication"],
    )

    assert requirements["hard_skills_required"] == ["Python"]
    assert requirements["soft_skills_required"] == ["Teamwork"]
    assert requirements["soft_skills_optional"] == ["Storytelling"]
    assert st.session_state[StateKeys.SKILL_BUCKETS] == {
        "must": ["Python", "Teamwork"],
        "nice": ["Storytelling"],
    }
    assert st.session_state[StateKeys.ESCO_MISSING_SKILLS] == []
    board_state = st.session_state[StateKeys.SKILL_BOARD_STATE]
    meta = st.session_state[StateKeys.SKILL_BOARD_META]
    esco_items = board_state["source_esco"]
    assert len(esco_items) == 1
    esco_identifier = esco_items[0]
    assert meta[esco_identifier]["label"] == "Communication"
    assert meta[esco_identifier]["source"] == "esco"


def test_skill_board_collects_extracted_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aggregated extracted fields land in the dedicated source container."""

    st.session_state.clear()
    st.session_state.lang = "de"
    st.session_state[StateKeys.SKILL_BOARD_STATE] = {}
    st.session_state[StateKeys.SKILL_BOARD_META] = {}

    requirements: dict[str, list[str]] = {
        "hard_skills_required": ["Python"],
        "hard_skills_optional": [],
        "soft_skills_required": [],
        "soft_skills_optional": [],
        "tools_and_technologies": ["Figma", "Notion"],
        "languages_required": ["English"],
        "languages_optional": ["German"],
        "certificates": ["PMP"],
    }

    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "header", lambda *_, **__: None)
    monkeypatch.setattr(st, "subheader", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "warning", lambda *_, **__: None)

    monkeypatch.setattr("wizard.sort_items", lambda items, **_: items)

    _render_skill_board(
        requirements,
        llm_suggestions={},
        esco_skills=[],
        missing_esco_skills=[],
    )

    board_state = st.session_state[StateKeys.SKILL_BOARD_STATE]
    meta = st.session_state[StateKeys.SKILL_BOARD_META]
    extracted_bucket = board_state["source_extracted"]
    extracted_labels = [meta[item]["label"] for item in extracted_bucket if item in meta]

    assert "Figma" in extracted_labels
    assert "Notion" in extracted_labels
    assert "English" in extracted_labels
    assert "German" in extracted_labels
    assert "PMP" in extracted_labels
