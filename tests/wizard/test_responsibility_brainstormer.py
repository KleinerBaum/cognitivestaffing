"""Regression tests for the responsibility brainstormer widget flow."""

from __future__ import annotations

from typing import Any, Callable

import pytest
import streamlit as st

import config
from constants.keys import StateKeys
from wizard.sections.responsibility_brainstormer import render_responsibility_brainstormer


class _DummyContext:
    def __enter__(self) -> "_DummyContext":
        return self

    def __exit__(self, *_args: object) -> bool:
        return False

    def markdown(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def caption(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def container(self) -> "_DummyContext":
        return self


class _DummyColumn(_DummyContext):
    def __init__(self, button_handler: Callable[[str | None], bool]):
        self._button_handler = button_handler

    def button(self, *_args: Any, key: str | None = None, **_kwargs: Any) -> bool:
        return self._button_handler(key)


def _install_streamlit_stubs(
    monkeypatch: pytest.MonkeyPatch, *, triggered_keys: set[str]
) -> None:
    def _button_handler(key: str | None) -> bool:
        if key and key in triggered_keys:
            triggered_keys.remove(key)
            return True
        return False

    def _fake_columns(spec: Any, *_args: Any, **_kwargs: Any) -> list[_DummyColumn]:
        if isinstance(spec, int):
            count = spec
        elif isinstance(spec, (list, tuple)):
            count = len(spec)
        else:
            count = 1
        return [_DummyColumn(_button_handler) for _ in range(max(1, count))]

    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "subheader", lambda *_, **__: None)
    monkeypatch.setattr(st, "write", lambda *_, **__: None)
    monkeypatch.setattr(st, "info", lambda *_, **__: None)
    monkeypatch.setattr(st, "button", lambda *_, key=None, **__: _button_handler(key))
    monkeypatch.setattr(st, "columns", _fake_columns)
    monkeypatch.setattr(st, "toast", lambda *_, **__: None)
    monkeypatch.setattr(st, "rerun", lambda *_, **__: None)
    monkeypatch.setattr(st, "container", lambda: _DummyContext())
    monkeypatch.setattr(st, "chat_message", lambda *_, **__: _DummyContext())
    monkeypatch.setattr(st, "chat_input", lambda *_, **__: None)
    monkeypatch.setattr(st, "expander", lambda *_, **__: _DummyContext())


def test_brainstormer_applies_suggestion_without_widget_collision(monkeypatch: pytest.MonkeyPatch) -> None:
    """Adding a suggestion should avoid session_state collisions across reruns."""

    st.session_state.clear()
    st.session_state.lang = "en"
    responsibilities_key = "ui.requirements.responsibilities"
    responsibilities_seed_key = f"{responsibilities_key}.__seed"
    suggested_key = f"{responsibilities_key}.__suggested"

    st.session_state[responsibilities_key] = "First bullet"
    st.session_state[responsibilities_seed_key] = "First bullet"
    st.session_state[StateKeys.RESPONSIBILITY_BRAINSTORMER] = {
        "messages": [
            {
                "role": "assistant",
                "content": "",
                "suggestions": ["Second bullet"],
            }
        ],
        "last_title": "Engineering Manager",
        "error": None,
    }

    triggered_keys = {f"{responsibilities_key}.chatkit.add.0.0"}
    _install_streamlit_stubs(monkeypatch, triggered_keys=triggered_keys)

    monkeypatch.setattr("config.CHATKIT_RESPONSIBILITIES_WORKFLOW_ID", None)

    render_responsibility_brainstormer(
        cleaned_responsibilities=["First bullet"],
        responsibilities_key=responsibilities_key,
        responsibilities_seed_key=responsibilities_seed_key,
        job_title="Engineering Manager",
        company_name="",
        team_structure="",
        industry="",
        tone_style=None,
        has_missing_key=False,
    )

    assert suggested_key in st.session_state

    if suggested_key in st.session_state:
        st.session_state[responsibilities_key] = st.session_state.pop(suggested_key)
        st.session_state[responsibilities_seed_key] = st.session_state[responsibilities_key]

    render_responsibility_brainstormer(
        cleaned_responsibilities=st.session_state[responsibilities_key].split("\n"),
        responsibilities_key=responsibilities_key,
        responsibilities_seed_key=responsibilities_seed_key,
        job_title="Engineering Manager",
        company_name="",
        team_structure="",
        industry="",
        tone_style=None,
        has_missing_key=False,
    )

    assert st.session_state[responsibilities_key] == "First bullet\nSecond bullet"
