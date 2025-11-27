from typing import Any

import streamlit as st

from constants.keys import StateKeys
from wizard.layout import render_step_heading, render_step_warning_banner


def test_render_step_warning_banner_includes_field_details(monkeypatch):
    """Warning banner should append details from the bilingual summary."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state[StateKeys.STEPPER_WARNING] = "⚠️ AI extraction was auto-repaired."
    st.session_state[StateKeys.EXTRACTION_SUMMARY] = {
        "Status": "⚠️ AI extraction was auto-repaired.",
        "Error details": "• company.contact_email: removed invalid value",
    }

    rendered: list[str] = []

    def _fake_markdown(body: str, unsafe_allow_html: bool = False) -> None:
        if "wizard-warning" in body:
            rendered.append(body)

    monkeypatch.setattr("wizard.layout.st.markdown", _fake_markdown)

    render_step_warning_banner()

    merged = "\n".join(rendered)
    assert "Validation notices" in merged or "Validierungshinweise" in merged
    assert "company.contact_email" in merged


def test_render_step_warning_banner_avoids_duplicate_summary(monkeypatch):
    """Summary strings identical to the warning should not repeat the text."""

    st.session_state.clear()
    warning_text = "⚠️ Extraction failed – please review the fields manually."
    st.session_state[StateKeys.STEPPER_WARNING] = warning_text
    st.session_state[StateKeys.EXTRACTION_SUMMARY] = warning_text

    rendered: list[str] = []

    def _fake_markdown(body: str, unsafe_allow_html: bool = False) -> None:
        if "wizard-warning" in body:
            rendered.append(body)

    monkeypatch.setattr("wizard.layout.st.markdown", _fake_markdown)

    render_step_warning_banner()

    merged = "\n".join(rendered)
    assert merged.count(warning_text) == 1


def test_render_step_warning_banner_surfaces_repair_fields(monkeypatch):
    """Profile repair metadata should render a bilingual warning banner."""

    st.session_state.clear()
    st.session_state.lang = "de"
    st.session_state[StateKeys.PROFILE_REPAIR_FIELDS] = {
        "auto_populated": ["company.name"],
        "removed": ["position.job_title"],
    }

    rendered: list[str] = []

    def _fake_markdown(body: str, unsafe_allow_html: bool = False) -> None:
        if "wizard-warning" in body:
            rendered.append(body)

    monkeypatch.setattr("wizard.layout.st.markdown", _fake_markdown)

    render_step_warning_banner()

    merged = "\n".join(rendered)
    assert "automatisch" in merged
    assert "Company Name" in merged
    assert "Position Job Title" in merged


def test_render_step_heading_uses_numeric_column_weights(monkeypatch):
    """Missing-field badge layout should avoid mixed numeric/string widths."""

    st.session_state.clear()

    captured: dict[str, Any] = {}

    class FakeColumn:
        def __init__(self, name: str) -> None:
            self.name = name
            self.headers: list[str] = []
            self.markdowns: list[tuple[str, bool]] = []

        def __enter__(self) -> "FakeColumn":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
            return False

        def header(self, text: str) -> None:
            self.headers.append(text)

        def markdown(self, text: str, unsafe_allow_html: bool = False) -> None:
            self.markdowns.append((text, unsafe_allow_html))

    def fake_columns(spec: tuple[float, float]):
        captured["spec"] = spec
        title_col = FakeColumn("title")
        badge_col = FakeColumn("badge")
        captured["columns"] = (title_col, badge_col)
        return title_col, badge_col

    monkeypatch.setattr("wizard.layout.st.columns", fake_columns)
    captured["headers"] = []

    def fake_header(text: str) -> None:
        captured["headers"].append(text)

    monkeypatch.setattr("wizard.layout.st.header", fake_header)

    render_step_heading("Company", missing_fields=("company.name",))

    assert captured["spec"] == (0.85, 0.15)
    assert all(isinstance(weight, (int, float)) for weight in captured["spec"])
    title_col, badge_col = captured["columns"]
    assert captured["headers"] == ["Company"]
    assert badge_col.markdowns, "Badge markdown should render when fields are missing"
