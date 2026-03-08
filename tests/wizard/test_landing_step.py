from __future__ import annotations

from typing import Any

import pytest
import streamlit as st

from constants.keys import StateKeys
from wizard.navigation_types import WizardContext
from wizard.steps.landing_step import step_landing


def _install_streamlit_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    text_input_values: dict[str, str],
    text_area_values: dict[str, str],
    continue_clicked: bool,
) -> None:
    monkeypatch.setattr(st, "header", lambda *_, **__: None)
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)

    def _text_input(
        _label: str,
        *,
        value: str = "",
        key: str | None = None,
        **_kwargs: Any,
    ) -> str:
        if key is not None and key in text_input_values:
            return text_input_values[key]
        return value

    def _text_area(
        _label: str,
        *,
        value: str = "",
        key: str | None = None,
        **_kwargs: Any,
    ) -> str:
        if key is not None and key in text_area_values:
            return text_area_values[key]
        return value

    def _button(_label: str, **_kwargs: Any) -> bool:
        return continue_clicked

    monkeypatch.setattr(st, "text_input", _text_input)
    monkeypatch.setattr(st, "text_area", _text_area)
    monkeypatch.setattr(st, "button", _button)


def test_landing_reads_primary_city_only(monkeypatch: pytest.MonkeyPatch) -> None:
    st.session_state.clear()
    st.session_state.lang = "de"
    st.session_state[StateKeys.PROFILE] = {
        "position": {"job_title": "Data Engineer"},
        "location": {"city": "Legacy City", "primary_city": "Berlin"},
    }

    captured_defaults: dict[str, str] = {}

    def _text_input(
        _label: str,
        *,
        value: str = "",
        key: str | None = None,
        **_kwargs: Any,
    ) -> str:
        if key is not None:
            captured_defaults[key] = value
        return value

    monkeypatch.setattr(st, "header", lambda *_, **__: None)
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "text_input", _text_input)
    monkeypatch.setattr(st, "text_area", lambda *_, value="", **__: value)
    monkeypatch.setattr(st, "button", lambda *_, **__: False)

    step_landing(WizardContext(schema={}, critical_fields=()))

    assert captured_defaults["landing.location.city"] == "Berlin"


def test_landing_persists_primary_city_without_state_requirement(monkeypatch: pytest.MonkeyPatch) -> None:
    st.session_state.clear()
    st.session_state.lang = "de"
    st.session_state[StateKeys.PROFILE] = {}

    _install_streamlit_stubs(
        monkeypatch,
        text_input_values={
            "landing.position.job_title": "  Software Engineer  ",
            "landing.location.city": "  Hamburg  ",
        },
        text_area_values={
            "landing.responsibilities.items": "Analyse\nAnalyse\nPlanung",
            "landing.requirements.hard_skills_required": "Python\nSQL",
            "landing.compensation.benefits": "Remote\nRemote",
        },
        continue_clicked=True,
    )

    updates: list[tuple[str, Any]] = []
    next_calls = 0

    def _update_profile(path: str, value: Any) -> None:
        updates.append((path, value))

    def _next_step() -> None:
        nonlocal next_calls
        next_calls += 1

    context = WizardContext(
        schema={},
        critical_fields=(),
        profile_updater=_update_profile,
        next_step_callback=_next_step,
    )

    step_landing(context)

    assert ("position.job_title", "Software Engineer") in updates
    assert ("location.primary_city", "Hamburg") in updates
    assert not any(path == "location.city" for path, _ in updates)
    assert not any(path == "location.state" for path, _ in updates)
    assert next_calls == 1
