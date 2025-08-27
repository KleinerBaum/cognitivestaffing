import pytest
import streamlit as st

from wizard import _autodetect_lang, _step_source, on_file_uploaded, on_url_changed
from constants.keys import StateKeys, UIKeys
from utils.session import bootstrap_session
from i18n import t
from models.need_analysis import NeedAnalysisProfile


class DummyTab:
    """Simple context manager stub for Streamlit tabs."""

    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def _setup_common(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch common Streamlit functions used in tests."""

    monkeypatch.setattr(st, "tabs", lambda labels: (DummyTab(), DummyTab(), DummyTab()))
    monkeypatch.setattr(st, "subheader", lambda *a, **k: None)
    monkeypatch.setattr(st, "file_uploader", lambda *a, **k: None)
    monkeypatch.setattr(st, "text_input", lambda *a, **k: "")
    monkeypatch.setattr(st, "success", lambda *a, **k: None)
    monkeypatch.setattr(st, "warning", lambda *a, **k: None)
    monkeypatch.setattr(st, "error", lambda *a, **k: None)
    monkeypatch.setattr(st, "write", lambda *a, **k: None)
    monkeypatch.setattr(st, "rerun", lambda: None)
    bootstrap_session()


def test_on_file_uploaded_populates_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Uploading a file populates JD text and text input state."""

    st.session_state.clear()
    st.session_state.lang = "en"
    sample_text = "from file"
    _setup_common(monkeypatch)
    monkeypatch.setattr("wizard.extract_text_from_file", lambda _f: sample_text)
    st.session_state[UIKeys.JD_FILE_UPLOADER] = object()

    on_file_uploaded()

    assert st.session_state.get(StateKeys.RAW_TEXT) == sample_text
    assert st.session_state.get(UIKeys.JD_TEXT_INPUT) == sample_text


def test_on_url_changed_populates_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """Entering a URL populates JD text and text input state."""

    st.session_state.clear()
    st.session_state.lang = "en"
    sample_text = "from url"
    _setup_common(monkeypatch)
    monkeypatch.setattr("wizard.extract_text_from_url", lambda _u: sample_text)
    st.session_state[UIKeys.JD_URL_INPUT] = "https://example.com"

    on_url_changed()

    assert st.session_state.get(StateKeys.RAW_TEXT) == sample_text
    assert st.session_state.get(UIKeys.JD_TEXT_INPUT) == sample_text


def test_on_url_changed_handles_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """on_url_changed should handle None text gracefully."""

    st.session_state.clear()
    st.session_state.lang = "en"
    _setup_common(monkeypatch)
    monkeypatch.setattr("wizard.extract_text_from_url", lambda _u: None)
    st.session_state[UIKeys.JD_URL_INPUT] = "https://example.com"

    on_url_changed()

    assert st.session_state.get(StateKeys.RAW_TEXT) == ""


@pytest.mark.parametrize("mode", ["text", "file", "url"])
def test_step_source_populates_data(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    """The source step should fill ``session_state[StateKeys.PROFILE]`` after analysis."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state.model = "gpt"
    sample_text = "Job text"
    sample_data = {"position": {"job_title": "Engineer"}}
    _setup_common(monkeypatch)
    analyze_label = t("analyze", st.session_state.lang)

    def fake_button(label: str, *a, **k) -> bool:
        return label == analyze_label

    monkeypatch.setattr(st, "button", fake_button)
    monkeypatch.setattr(
        "wizard.extract_with_function", lambda _t, _s, model=None: sample_data
    )
    monkeypatch.setattr("wizard.search_occupation", lambda _t, _l: None)

    if mode == "file":
        monkeypatch.setattr("wizard.extract_text_from_file", lambda _f: sample_text)
        st.session_state[UIKeys.JD_FILE_UPLOADER] = object()
        on_file_uploaded()
    elif mode == "url":
        monkeypatch.setattr("wizard.extract_text_from_url", lambda _u: sample_text)
        st.session_state[UIKeys.JD_URL_INPUT] = "https://example.com"
        on_url_changed()
    else:
        st.session_state[StateKeys.RAW_TEXT] = sample_text
        st.session_state[UIKeys.JD_TEXT_INPUT] = sample_text

    monkeypatch.setattr(
        st, "text_area", lambda *a, **k: st.session_state.get(UIKeys.JD_TEXT_INPUT, "")
    )

    _step_source({})

    data = st.session_state[StateKeys.PROFILE]
    assert data["position"]["job_title"] == "Engineer"


def test_step_source_merges_esco_skills(monkeypatch: pytest.MonkeyPatch) -> None:
    """Essential skills from ESCO are merged into hard skills without duplicates."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state.model = "gpt"
    st.session_state[StateKeys.STEP] = 0
    sample_text = "Job text"
    st.session_state[StateKeys.RAW_TEXT] = sample_text
    st.session_state[UIKeys.JD_TEXT_INPUT] = sample_text
    sample_data = {
        "position": {"job_title": "Engineer"},
        "requirements": {"hard_skills": ["Python"]},
    }
    _setup_common(monkeypatch)
    analyze_label = t("analyze", st.session_state.lang)

    def fake_button(label: str, *a, **k) -> bool:
        return label == analyze_label

    monkeypatch.setattr(st, "button", fake_button)
    monkeypatch.setattr(st, "text_area", lambda *a, **k: sample_text)
    monkeypatch.setattr(
        "wizard.extract_with_function", lambda _t, _s, model=None: sample_data
    )
    monkeypatch.setattr(
        "wizard.search_occupation",
        lambda _t, _l: {
            "preferredLabel": "software developer",
            "uri": "http://example.com/occ",
            "group": "Software developers",
        },
    )
    monkeypatch.setattr(
        "wizard.enrich_skills",
        lambda _u, _l: ["Python", "Project management"],
    )

    _step_source({})

    data = st.session_state[StateKeys.PROFILE]
    assert data["position"]["occupation_label"] == "software developer"
    assert data["position"]["occupation_uri"] == "http://example.com/occ"
    assert data["requirements"]["hard_skills"] == [
        "Project management",
        "Python",
    ]


def test_step_source_skip_creates_empty_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Skipping analysis should create an empty profile and advance the step."""

    st.session_state.clear()
    st.session_state.lang = "en"
    _setup_common(monkeypatch)

    monkeypatch.setattr(
        st,
        "text_area",
        lambda *a, **k: st.session_state.get(UIKeys.JD_TEXT_INPUT, ""),
    )

    skip_label = "Continue without template"

    def fake_button(label: str, *a, **k) -> bool:
        return label == skip_label

    monkeypatch.setattr(st, "button", fake_button)

    _step_source({})

    assert st.session_state[StateKeys.STEP] == 2
    assert st.session_state[StateKeys.PROFILE] == NeedAnalysisProfile().model_dump()


@pytest.mark.parametrize("mode", ["file", "url"])
def test_on_change_handles_extraction_errors(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """Extraction errors should show a message and keep JD text unchanged."""

    st.session_state.clear()
    st.session_state.lang = "en"
    _setup_common(monkeypatch)
    errors: list[str] = []
    monkeypatch.setattr(st, "error", lambda msg, *a, **k: errors.append(str(msg)))

    if mode == "file":

        def raise_err(_f):
            raise ValueError("bad file")

        monkeypatch.setattr("wizard.extract_text_from_file", raise_err)
        st.session_state[UIKeys.JD_FILE_UPLOADER] = object()
        on_file_uploaded()
    else:

        def raise_err(_u):
            raise ValueError("bad url")

        monkeypatch.setattr("wizard.extract_text_from_url", raise_err)
        st.session_state[UIKeys.JD_URL_INPUT] = "https://example.com"
        on_url_changed()

    assert st.session_state.get(StateKeys.RAW_TEXT, "") == ""
    assert errors, "Expected st.error to be called"


def test_autodetect_lang_sets_en() -> None:
    """_autodetect_lang should switch language based on text content."""

    st.session_state.clear()
    st.session_state.lang = "de"

    _autodetect_lang("This is an English job description.")

    assert st.session_state.lang == "en"
