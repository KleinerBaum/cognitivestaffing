from __future__ import annotations

import pytest
import streamlit as st

from constants.keys import StateKeys, UIKeys
from wizard import _render_esco_occupation_selector


def test_render_esco_occupation_selector_updates_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Selecting an ESCO occupation should update position metadata."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state[StateKeys.PROFILE] = {"position": {}}
    position = st.session_state[StateKeys.PROFILE]["position"]
    st.session_state[StateKeys.ESCO_OCCUPATION_OPTIONS] = [
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

    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "button", lambda *_, **__: False)
    monkeypatch.setattr(st, "rerun", lambda *_, **__: None)

    class DummyColumn:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def fake_columns(spec, *_args, **_kwargs):
        if isinstance(spec, int):
            count = spec
        elif isinstance(spec, (list, tuple)):
            count = len(spec)
        else:
            count = 2
        return [DummyColumn() for _ in range(max(count, 1))]

    monkeypatch.setattr(st, "columns", fake_columns)

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
        assert key == UIKeys.POSITION_ESCO_OCCUPATION
        assert st.session_state[key] == []
        assert any("Data Analyst" in format_func(opt) for opt in options)
        assert kwargs.get("label_visibility") == "collapsed"
        assert "ESCO" in kwargs.get("placeholder", "")
        st.session_state[key] = ["uri:2"]
        on_change()
        return ["uri:2"]

    monkeypatch.setattr(st, "multiselect", fake_multiselect)

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
