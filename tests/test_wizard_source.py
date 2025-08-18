"""Tests for the wizard's source step."""

from __future__ import annotations

import pytest
import streamlit as st
from streamlit.errors import StreamlitAPIException

from wizard import _step_source


class DummyTab:
    """Simple context manager stub for Streamlit tabs."""

    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False


def test_step_source_file_upload_sets_jd_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uploading a file should set ``jd_text`` and populate the text area."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state.model = "gpt"
    sample_text = "from file"

    monkeypatch.setattr(st, "tabs", lambda labels: (DummyTab(), DummyTab(), DummyTab()))
    monkeypatch.setattr(st, "subheader", lambda *a, **k: None)
    monkeypatch.setattr(st, "error", lambda *a, **k: None)

    button_calls = iter([True, False])
    monkeypatch.setattr(st, "button", lambda *a, **k: next(button_calls))
    monkeypatch.setattr(st, "file_uploader", lambda *a, **k: object())
    monkeypatch.setattr(st, "text_input", lambda *a, **k: "")
    monkeypatch.setattr(
        st, "text_area", lambda *a, **k: st.session_state.get("jd_text", "")
    )
    monkeypatch.setattr(
        "utils.pdf_utils.extract_text_from_file", lambda _f: sample_text
    )

    reran: dict[str, bool] = {"called": False}
    monkeypatch.setattr(st, "rerun", lambda: reran.update(called=True))

    try:
        _step_source({})
    except StreamlitAPIException as e:  # pragma: no cover - defensive
        pytest.fail(f"StreamlitAPIException raised: {e}")

    assert st.session_state["jd_text"] == sample_text
    assert reran["called"]

    button_calls = iter([False])
    monkeypatch.setattr(st, "button", lambda *a, **k: next(button_calls, False))
    monkeypatch.setattr(st, "file_uploader", lambda *a, **k: None)
    monkeypatch.setattr(st, "text_input", lambda *a, **k: "")

    captured: dict[str, str] = {}

    def text_area_capture(*_a, **_k):
        captured["value"] = st.session_state.get("jd_text", "")
        return captured["value"]

    monkeypatch.setattr(st, "text_area", text_area_capture)

    _step_source({})

    assert captured["value"] == sample_text


def test_step_source_url_upload_sets_jd_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uploading via URL should set ``jd_text`` and populate the text area."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state.model = "gpt"
    sample_text = "from url"

    monkeypatch.setattr(st, "tabs", lambda labels: (DummyTab(), DummyTab(), DummyTab()))
    monkeypatch.setattr(st, "subheader", lambda *a, **k: None)
    monkeypatch.setattr(st, "error", lambda *a, **k: None)

    button_calls = iter([True, False])
    monkeypatch.setattr(st, "button", lambda *a, **k: next(button_calls))
    monkeypatch.setattr(st, "file_uploader", lambda *a, **k: None)
    monkeypatch.setattr(st, "text_input", lambda *a, **k: "https://example.com")
    monkeypatch.setattr(
        st, "text_area", lambda *a, **k: st.session_state.get("jd_text", "")
    )
    monkeypatch.setattr("utils.url_utils.extract_text_from_url", lambda _u: sample_text)

    reran: dict[str, bool] = {"called": False}
    monkeypatch.setattr(st, "rerun", lambda: reran.update(called=True))

    try:
        _step_source({})
    except StreamlitAPIException as e:  # pragma: no cover - defensive
        pytest.fail(f"StreamlitAPIException raised: {e}")

    assert st.session_state["jd_text"] == sample_text
    assert reran["called"]

    button_calls = iter([False])
    monkeypatch.setattr(st, "button", lambda *a, **k: next(button_calls, False))
    monkeypatch.setattr(st, "file_uploader", lambda *a, **k: None)
    monkeypatch.setattr(st, "text_input", lambda *a, **k: "")

    captured: dict[str, str] = {}

    def text_area_capture(*_a, **_k):
        captured["value"] = st.session_state.get("jd_text", "")
        return captured["value"]

    monkeypatch.setattr(st, "text_area", text_area_capture)

    _step_source({})

    assert captured["value"] == sample_text


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


def test_step_source_merges_esco_skills(monkeypatch: pytest.MonkeyPatch) -> None:
    """Essential skills from ESCO are merged into hard skills without dups."""
    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state.model = "gpt"
    st.session_state.step = 0
    sample_text = "Job text"
    sample_data = {
        "position": {"job_title": "Engineer"},
        "requirements": {"hard_skills": ["Python"]},
    }

    # Streamlit stubs
    monkeypatch.setattr(st, "tabs", lambda labels: (DummyTab(), DummyTab(), DummyTab()))
    monkeypatch.setattr(st, "subheader", lambda *a, **k: None)
    monkeypatch.setattr(st, "success", lambda *a, **k: None)
    monkeypatch.setattr(st, "warning", lambda *a, **k: None)
    monkeypatch.setattr(st, "error", lambda *a, **k: None)
    monkeypatch.setattr(st, "rerun", lambda: None)
    monkeypatch.setattr(st, "button", lambda *a, **k: True)
    monkeypatch.setattr(st, "text_area", lambda *a, **k: sample_text)
    monkeypatch.setattr(st, "file_uploader", lambda *a, **k: None)
    monkeypatch.setattr(st, "text_input", lambda *a, **k: "")

    # Extraction and ESCO helpers
    monkeypatch.setattr(
        "wizard.extract_with_function", lambda _t, _s, model=None: sample_data
    )
    monkeypatch.setattr(
        "wizard.classify_occupation",
        lambda _t, _l: {
            "preferredLabel": "software developer",
            "uri": "http://example.com/occ",
            "group": "Software developers",
        },
    )
    monkeypatch.setattr(
        "wizard.get_essential_skills",
        lambda _u, _l: ["Python", "Project management"],
    )

    _step_source({})

    data = st.session_state.data
    assert data["position"]["occupation_label"] == "software developer"
    assert data["position"]["occupation_uri"] == "http://example.com/occ"
    assert data["requirements"]["hard_skills"] == [
        "Project management",
        "Python",
    ]


@pytest.mark.parametrize("mode", ["file", "url"])
def test_step_source_handles_extraction_errors(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """Extraction errors should show a message and keep ``jd_text`` unchanged."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state.model = "gpt"
    st.session_state.jd_text = ""
    errors: list[str] = []

    monkeypatch.setattr(st, "tabs", lambda labels: (DummyTab(), DummyTab(), DummyTab()))
    monkeypatch.setattr(st, "subheader", lambda *a, **k: None)
    monkeypatch.setattr(st, "warning", lambda *a, **k: None)
    monkeypatch.setattr(st, "rerun", lambda: None)
    monkeypatch.setattr(st, "button", lambda *a, **k: True)
    monkeypatch.setattr(st, "error", lambda msg, *a, **k: errors.append(str(msg)))

    if mode == "file":
        monkeypatch.setattr(st, "text_area", lambda *a, **k: "")
        monkeypatch.setattr(st, "file_uploader", lambda *a, **k: object())
        monkeypatch.setattr(st, "text_input", lambda *a, **k: "")

        def raise_value_error(_f):  # pragma: no cover - test stub
            raise ValueError("bad file")

        monkeypatch.setattr("utils.pdf_utils.extract_text_from_file", raise_value_error)
    else:  # url
        monkeypatch.setattr(st, "text_area", lambda *a, **k: "")
        monkeypatch.setattr(st, "file_uploader", lambda *a, **k: None)
        monkeypatch.setattr(st, "text_input", lambda *a, **k: "https://example.com")

        def raise_value_error(_u):  # pragma: no cover - test stub
            raise ValueError("bad url")

        monkeypatch.setattr("utils.url_utils.extract_text_from_url", raise_value_error)

    monkeypatch.setattr("wizard.extract_with_function", lambda _t, _s, model=None: {})
    monkeypatch.setattr("wizard.classify_occupation", lambda _t, _l: None)

    _step_source({})

    assert st.session_state.jd_text == ""
    assert errors, "Expected st.error to be called"
