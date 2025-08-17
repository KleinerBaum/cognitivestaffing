"""Tests for the wizard's source step."""

from __future__ import annotations

import streamlit as st
import pytest

from wizard import _step_source


class DummyTab:
    """Simple context manager stub for Streamlit tabs."""

    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.mark.parametrize("mode", ["text", "file", "url"])
def test_step_source_populates_data(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    """The source step should fill ``session_state.data`` after analysis."""
    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state.model = "gpt"
    sample_text = "Job text"
    sample_data = {"position": {"job_title": "Engineer"}}

    # Streamlit UI stubs
    monkeypatch.setattr(st, "tabs", lambda labels: (DummyTab(), DummyTab(), DummyTab()))
    monkeypatch.setattr(st, "subheader", lambda *a, **k: None)
    monkeypatch.setattr(st, "success", lambda *a, **k: None)
    monkeypatch.setattr(st, "warning", lambda *a, **k: None)
    monkeypatch.setattr(st, "error", lambda *a, **k: None)
    monkeypatch.setattr(st, "rerun", lambda: None)
    monkeypatch.setattr(st, "button", lambda *a, **k: True)

    if mode == "text":
        monkeypatch.setattr(st, "text_area", lambda *a, **k: sample_text)
        monkeypatch.setattr(st, "file_uploader", lambda *a, **k: None)
        monkeypatch.setattr(st, "text_input", lambda *a, **k: "")
    elif mode == "file":
        monkeypatch.setattr(st, "text_area", lambda *a, **k: "")
        monkeypatch.setattr(st, "file_uploader", lambda *a, **k: object())
        monkeypatch.setattr(st, "text_input", lambda *a, **k: "")
        monkeypatch.setattr(
            "utils.pdf_utils.extract_text_from_file", lambda _f: sample_text
        )
    else:  # url
        monkeypatch.setattr(st, "text_area", lambda *a, **k: "")
        monkeypatch.setattr(st, "file_uploader", lambda *a, **k: None)
        monkeypatch.setattr(st, "text_input", lambda *a, **k: "https://example.com")
        monkeypatch.setattr(
            "utils.url_utils.extract_text_from_url", lambda _u: sample_text
        )

    # Extraction helpers
    monkeypatch.setattr(
        "wizard.extract_with_function", lambda _t, _s, model=None: sample_data
    )
    monkeypatch.setattr("wizard.classify_occupation", lambda _t, _l: None)

    _step_source({})

    assert st.session_state.data == sample_data
