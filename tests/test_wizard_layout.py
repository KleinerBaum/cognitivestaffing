import streamlit as st

from constants.keys import StateKeys
from wizard.layout import render_step_warning_banner


def test_render_step_warning_banner_includes_field_details(monkeypatch):
    """Warning banner should append details from the bilingual summary."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state[StateKeys.STEPPER_WARNING] = "⚠️ AI extraction was auto-repaired."
    st.session_state[StateKeys.EXTRACTION_SUMMARY] = {
        "Status": "⚠️ AI extraction was auto-repaired.",
        "Error details": "• company.contact_email: removed invalid value",
    }

    captured: dict[str, str] = {}

    def _fake_warning(message: str) -> None:
        captured["message"] = message

    monkeypatch.setattr("wizard.layout.st.warning", _fake_warning)

    render_step_warning_banner()

    assert "Details" in captured["message"]
    assert "company.contact_email" in captured["message"]


def test_render_step_warning_banner_avoids_duplicate_summary(monkeypatch):
    """Summary strings identical to the warning should not repeat the text."""

    st.session_state.clear()
    warning_text = "⚠️ Extraction failed – please review the fields manually."
    st.session_state[StateKeys.STEPPER_WARNING] = warning_text
    st.session_state[StateKeys.EXTRACTION_SUMMARY] = warning_text

    captured: dict[str, str] = {}

    def _fake_warning(message: str) -> None:
        captured["message"] = message

    monkeypatch.setattr("wizard.layout.st.warning", _fake_warning)

    render_step_warning_banner()

    assert captured["message"] == warning_text


def test_render_step_warning_banner_surfaces_repair_fields(monkeypatch):
    """Profile repair metadata should render a bilingual warning banner."""

    st.session_state.clear()
    st.session_state.lang = "de"
    st.session_state[StateKeys.PROFILE_REPAIR_FIELDS] = {
        "auto_populated": ["company.name"],
        "removed": ["position.job_title"],
    }

    captured: dict[str, str] = {}

    def _fake_warning(message: str) -> None:
        captured["message"] = message

    monkeypatch.setattr("wizard.layout.st.warning", _fake_warning)

    render_step_warning_banner()

    assert "automatisch" in captured["message"]
    assert "Company Name" in captured["message"]
    assert "Position Job Title" in captured["message"]
