import streamlit as st
import pytest

from constants.keys import UIKeys
from wizard import _step_onboarding


class DummyContext:
    """Lightweight context manager used to stub column blocks."""

    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - interface only
        return None


def test_onboarding_language_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Onboarding mirrors the sidebar language choice into ``st.session_state.lang``."""

    st.session_state.clear()
    st.session_state.lang = "de"
    st.session_state[UIKeys.INPUT_METHOD] = "text"
    st.session_state[UIKeys.LANG_SELECT] = "en"

    def fake_radio(label, options, *, key, horizontal=False, on_change=None, **kwargs):
        if key == UIKeys.INPUT_METHOD:
            return st.session_state.get(UIKeys.INPUT_METHOD, options[0])
        return options[0]

    monkeypatch.setattr(st, "radio", fake_radio)
    monkeypatch.setattr(st, "markdown", lambda *a, **k: None)
    monkeypatch.setattr(st, "write", lambda *a, **k: None)
    monkeypatch.setattr(st, "checkbox", lambda *a, **k: False)
    monkeypatch.setattr(st, "columns", lambda *a, **k: (DummyContext(), DummyContext()))
    monkeypatch.setattr(st, "info", lambda *a, **k: None)
    monkeypatch.setattr(st, "file_uploader", lambda *a, **k: None)
    monkeypatch.setattr(st, "image", lambda *a, **k: None)
    monkeypatch.setattr(st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(st, "button", lambda *a, **k: False)
    monkeypatch.setattr(st, "rerun", lambda: None)
    monkeypatch.setattr("wizard._maybe_run_extraction", lambda schema: None)

    _step_onboarding({})

    assert st.session_state.lang == "en"
