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

    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)

    def fake_radio(label, *, options, index, key, format_func):
        assert key == UIKeys.POSITION_ESCO_OCCUPATION
        assert options[index] == "__none__"
        assert any("Data Analyst" in format_func(opt) for opt in options)
        return "uri:2"

    monkeypatch.setattr(st, "radio", fake_radio)

    _render_esco_occupation_selector(position)

    assert position["occupation_label"] == "Data Analyst"
    assert position["occupation_uri"] == "uri:2"
    assert position["occupation_group"] == "Science professionals"
