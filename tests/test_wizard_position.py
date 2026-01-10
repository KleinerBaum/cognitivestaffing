from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Callable

import pytest
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from constants.keys import StateKeys, UIKeys
from wizard import _apply_esco_selection, _render_esco_occupation_selector


pytestmark = pytest.mark.integration


class _DummyContainer:
    def __init__(self, multiselect_handler: Callable[..., Any]):
        self._multiselect_handler = multiselect_handler

    def __enter__(self) -> "_DummyContainer":
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def markdown(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def caption(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def button(self, *_args: Any, **_kwargs: Any) -> bool:
        return False

    def container(self) -> "_DummyContainer":
        return self

    def columns(self, spec: Any, *_args: Any, **_kwargs: Any) -> list["_DummyColumn"]:
        if isinstance(spec, int):
            count = spec
        elif isinstance(spec, (list, tuple)):
            count = len(spec)
        else:
            count = 2
        return [_DummyColumn(self._multiselect_handler) for _ in range(max(count, 1))]

    def multiselect(self, *args: Any, **kwargs: Any) -> Any:
        return self._multiselect_handler(*args, **kwargs)


class _DummyColumn(_DummyContainer):
    pass


def _install_streamlit_fakes(
    monkeypatch: pytest.MonkeyPatch,
    *,
    multiselect_handler: Callable[..., Any],
) -> None:
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "button", lambda *_, **__: False)
    monkeypatch.setattr(st, "rerun", lambda *_, **__: None)
    monkeypatch.setattr(st, "multiselect", multiselect_handler)

    def _fake_columns(spec: Any, *_args: Any, **_kwargs: Any) -> list[_DummyColumn]:
        return _DummyContainer(multiselect_handler).columns(spec, *_args, **_kwargs)

    monkeypatch.setattr(st, "columns", _fake_columns)
    monkeypatch.setattr(st, "container", lambda: _DummyContainer(multiselect_handler))


def test_render_esco_occupation_selector_updates_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Selecting an ESCO occupation should update position metadata."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state[StateKeys.PROFILE] = {"position": {}}
    position = st.session_state[StateKeys.PROFILE]["position"]
    st.session_state[StateKeys.UI_ESCO_OCCUPATION_OPTIONS] = [
        {
            "preferredLabel": "Data Scientist",
            "group": "Science professionals",
            "uri": "uri:1",
        },
        {
            "preferredLabel": "Data Analyst",
            "group": "Science professionals",
            "uri": "uri:2",
        },
    ]
    st.session_state[StateKeys.ESCO_SELECTED_OCCUPATIONS] = []
    st.session_state[StateKeys.REQUIREMENTS_ESCO_OPT_IN] = True

    skill_store: dict[str, list[str]] = {
        "uri:1": ["Python"],
        "uri:2": ["SQL"],
    }

    monkeypatch.setattr(
        "wizard.get_essential_skills",
        lambda uri, **_: skill_store.get(uri, []),
    )

    def fake_multiselect(
        label,
        *,
        options,
        key,
        format_func,
        on_change,
        **kwargs,
    ):
        assert key == UIKeys.POSITION_ESCO_OCCUPATION_WIDGET
        assert st.session_state[key] == []
        assert any("Data Analyst" in format_func(opt) for opt in options)
        assert kwargs.get("label_visibility") == "collapsed"
        assert "ESCO" in kwargs.get("placeholder", "")
        st.session_state[key] = ["uri:2"]
        on_change()
        return ["uri:2"]

    _install_streamlit_fakes(monkeypatch, multiselect_handler=fake_multiselect)

    _render_esco_occupation_selector(position)

    assert position["occupation_label"] == "Data Analyst"
    assert position["occupation_uri"] == "uri:2"
    assert position["occupation_group"] == "Science professionals"
    assert st.session_state[StateKeys.ESCO_SELECTED_OCCUPATIONS] == [
        {
            "preferredLabel": "Data Analyst",
            "group": "Science professionals",
            "uri": "uri:2",
        }
    ]
    assert st.session_state[StateKeys.ESCO_SKILLS] == ["SQL"]


def test_render_esco_occupation_selector_consumes_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Override state should pre-populate the selector and be cleared."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state[StateKeys.PROFILE] = {"position": {}}
    position = st.session_state[StateKeys.PROFILE]["position"]
    st.session_state[StateKeys.UI_ESCO_OCCUPATION_OPTIONS] = [
        {
            "preferredLabel": "Data Scientist",
            "group": "Science professionals",
            "uri": "uri:1",
        },
        {
            "preferredLabel": "Data Analyst",
            "group": "Science professionals",
            "uri": "uri:2",
        },
    ]
    st.session_state[StateKeys.ESCO_SELECTED_OCCUPATIONS] = []
    st.session_state[StateKeys.REQUIREMENTS_ESCO_OPT_IN] = True
    st.session_state[UIKeys.POSITION_ESCO_OCCUPATION] = ["uri:2"]
    st.session_state[StateKeys.UI_ESCO_OCCUPATION_OVERRIDE] = ["uri:1"]

    skill_store: dict[str, list[str]] = {
        "uri:1": ["Python"],
        "uri:2": ["SQL"],
    }

    monkeypatch.setattr(
        "wizard.get_essential_skills",
        lambda uri, **_: skill_store.get(uri, []),
    )

    captured_calls: list[list[str]] = []
    original_apply = _apply_esco_selection

    def fake_apply(selected_ids, options, *, lang):
        captured_calls.append(list(selected_ids))
        return original_apply(selected_ids, options, lang=lang)

    monkeypatch.setattr("wizard._apply_esco_selection", fake_apply)

    def fake_multiselect(
        label,
        *,
        options,
        key,
        format_func,
        on_change,
        **kwargs,
    ):
        assert key == UIKeys.POSITION_ESCO_OCCUPATION_WIDGET
        assert st.session_state[key] == ["uri:1"]
        assert StateKeys.UI_ESCO_OCCUPATION_OVERRIDE not in st.session_state
        assert any("Data Scientist" in format_func(opt) for opt in options)
        assert kwargs.get("label_visibility") == "collapsed"
        return st.session_state[key]

    _install_streamlit_fakes(monkeypatch, multiselect_handler=fake_multiselect)

    _render_esco_occupation_selector(position)

    assert captured_calls and captured_calls[-1] == ["uri:1"]
    assert st.session_state[UIKeys.POSITION_ESCO_OCCUPATION] == ["uri:1"]
    assert StateKeys.UI_ESCO_OCCUPATION_OVERRIDE not in st.session_state
    assert position["occupation_uri"] == "uri:1"
    assert st.session_state[StateKeys.ESCO_SELECTED_OCCUPATIONS] == [
        {
            "preferredLabel": "Data Scientist",
            "group": "Science professionals",
            "uri": "uri:1",
        }
    ]
    assert st.session_state[StateKeys.ESCO_SKILLS] == ["Python"]
