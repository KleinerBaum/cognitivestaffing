import streamlit as st
import pytest
from typing import Literal

from wizard import _field_label, _step_summary
from constants.keys import StateKeys
from question_logic import CRITICAL_FIELDS
from models.need_analysis import NeedAnalysisProfile


def test_field_label_known() -> None:
    st.session_state.lang = "en"
    assert _field_label("company.name") == "Company Name"


def test_field_label_fallback() -> None:
    st.session_state.lang = "en"
    assert _field_label("compensation.salary_min") == "Compensation Salary Min"


def test_summary_warning_uses_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    """Summary step warning should display human-friendly labels."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state[StateKeys.PROFILE] = NeedAnalysisProfile().model_dump()

    captured: dict[str, str] = {}
    monkeypatch.setattr(st, "warning", lambda msg: captured.setdefault("msg", msg))

    class DummyTab:
        def __enter__(self) -> None:  # pragma: no cover - trivial
            return None

        def __exit__(
            self, exc_type, exc, tb
        ) -> Literal[False]:  # pragma: no cover - trivial
            return False

    monkeypatch.setattr(st, "tabs", lambda labels: [DummyTab() for _ in labels])
    monkeypatch.setattr("wizard._summary_company", lambda: None)
    monkeypatch.setattr("wizard._summary_position", lambda: None)
    monkeypatch.setattr("wizard._summary_requirements", lambda: None)
    monkeypatch.setattr("wizard._summary_employment", lambda: None)
    monkeypatch.setattr("wizard._summary_compensation", lambda: None)
    monkeypatch.setattr("wizard._summary_process", lambda: None)

    _step_summary({}, list(CRITICAL_FIELDS))

    msg = captured.get("msg", "")
    assert "Company Name" in msg
    assert "Job Title" in msg
    assert "company.name" not in msg
