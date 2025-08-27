import streamlit as st
import pytest

from wizard import _step_intro
from utils.session import bootstrap_session


def test_step_intro_language_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Language radio should update ``st.session_state.lang``."""

    st.session_state.clear()
    bootstrap_session()
    st.session_state.lang = "de"

    def fake_radio(label, options, key, horizontal=False, on_change=None):
        st.session_state[key] = "English"
        if on_change:
            on_change()
        return "English"

    monkeypatch.setattr(st, "radio", fake_radio)
    monkeypatch.setattr(st, "header", lambda *a, **k: None)
    monkeypatch.setattr(st, "write", lambda *a, **k: None)
    monkeypatch.setattr(st, "subheader", lambda *a, **k: None)
    monkeypatch.setattr(st, "markdown", lambda *a, **k: None)

    _step_intro()

    assert st.session_state.lang == "en"
