"""Localization regression tests for wizard labels."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from constants.keys import StateKeys
from wizard import _step_compensation, _summary_compensation, run_wizard


def _base_profile() -> dict[str, dict]:
    return {
        "compensation": {
            "salary_min": 50000,
            "salary_max": 70000,
            "currency": "EUR",
            "period": "year",
            "variable_pay": False,
            "bonus_percentage": None,
            "commission_structure": "",
            "equity_offered": False,
            "benefits": [],
        },
        "position": {"job_title": ""},
        "company": {"industry": ""},
    }


class _Column:
    """Lightweight stub mimicking ``st.columns`` return value."""

    def __init__(self, toggle_recorder: list[str]):
        self._toggle_recorder = toggle_recorder

    def __enter__(self) -> "_Column":  # pragma: no cover - context protocol
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # pragma: no cover - context protocol
        return None

    def selectbox(self, label: str, *, options, index=0, **kwargs):  # pragma: no cover
        return options[index]

    def toggle(self, label: str, *, value=False, **kwargs):
        self._toggle_recorder.append(label)
        return value

    def text_input(self, label: str, *, value="", **kwargs):  # pragma: no cover - passthrough
        return value

    def number_input(self, label: str, *, value=0, **kwargs):  # pragma: no cover - passthrough
        return value

    def text_area(self, label: str, *, value="", **kwargs):  # pragma: no cover - passthrough
        return value


def _patch_columns(monkeypatch: pytest.MonkeyPatch, toggle_recorder: list[str]) -> None:
    def fake_columns(spec):
        count = spec if isinstance(spec, int) else len(spec)
        return tuple(_Column(toggle_recorder) for _ in range(count))

    monkeypatch.setattr(st, "columns", fake_columns)


def _patch_common_streamlit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(st, "subheader", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "button", lambda *_, **__: False)
    monkeypatch.setattr(st, "slider", lambda *_, value, **__: value)
    monkeypatch.setattr(st, "multiselect", lambda *_, default, **__: default)


@pytest.mark.parametrize(
    "lang,expected_equity,expected_benefits",
    [
        ("de", "Mitarbeiterbeteiligung?", "Leistungen"),
        ("en", "Equity?", "Benefits"),
    ],
)
def test_step_compensation_localizes_labels(
    monkeypatch: pytest.MonkeyPatch,
    lang: str,
    expected_equity: str,
    expected_benefits: str,
) -> None:
    toggle_labels: list[str] = []
    chip_labels: list[str] = []

    st.session_state.clear()
    st.session_state[StateKeys.PROFILE] = _base_profile()
    st.session_state[StateKeys.BENEFIT_SUGGESTIONS] = []
    st.session_state["lang"] = lang

    _patch_columns(monkeypatch, toggle_labels)
    _patch_common_streamlit(monkeypatch)

    monkeypatch.setattr(
        "wizard._chip_multiselect",
        lambda label, *, options, values, **__: chip_labels.append(label) or values,
    )

    _step_compensation()

    assert expected_equity in toggle_labels
    assert expected_benefits in chip_labels


@pytest.mark.parametrize(
    "lang,expected_equity,expected_benefits",
    [
        ("de", "Mitarbeiterbeteiligung?", "Leistungen"),
        ("en", "Equity?", "Benefits"),
    ],
)
def test_summary_compensation_localizes_labels(
    monkeypatch: pytest.MonkeyPatch,
    lang: str,
    expected_equity: str,
    expected_benefits: str,
) -> None:
    toggle_labels: list[str] = []
    chip_labels: list[str] = []

    st.session_state.clear()
    st.session_state[StateKeys.PROFILE] = _base_profile()
    st.session_state["lang"] = lang

    _patch_columns(monkeypatch, toggle_labels)
    _patch_common_streamlit(monkeypatch)

    monkeypatch.setattr(
        "wizard._chip_multiselect",
        lambda label, *, options, values, **__: chip_labels.append(label) or values,
    )
    monkeypatch.setattr("wizard._update_profile", lambda *_, **__: None)

    _summary_compensation()

    assert expected_equity in toggle_labels
    assert expected_benefits in chip_labels


@pytest.mark.parametrize(
    "lang,expected_home,expected_donate",
    [
        ("de", "🏠 Startseite", "❤️ Entwickler unterstützen"),
        ("en", "🏠 Home", "❤️ Donate to the developer"),
    ],
)
def test_summary_footer_uses_translations(
    monkeypatch: pytest.MonkeyPatch,
    lang: str,
    expected_home: str,
    expected_donate: str,
) -> None:
    st.session_state.clear()
    st.session_state["lang"] = lang
    st.session_state[StateKeys.STEP] = 6
    st.session_state[StateKeys.PROFILE] = _base_profile()
    st.session_state["_schema"] = {"fields": []}
    st.session_state["_critical_list"] = []
    st.session_state[StateKeys.FOLLOWUPS] = []
    st.session_state[StateKeys.USAGE] = None

    button_labels: list[str] = []

    class _ColumnCtx:
        def __enter__(self):  # pragma: no cover - context protocol
            return None

        def __exit__(self, exc_type, exc, tb):  # pragma: no cover - context protocol
            return None

    def fake_columns(spec):
        count = spec if isinstance(spec, int) else len(spec)
        return tuple(_ColumnCtx() for _ in range(count))

    monkeypatch.setattr(st, "columns", fake_columns)
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "divider", lambda *_, **__: None)
    monkeypatch.setattr(st, "info", lambda *_, **__: None)
    monkeypatch.setattr(st, "warning", lambda *_, **__: None)
    monkeypatch.setattr(st, "success", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "button", lambda label, *_, **__: button_labels.append(label) or False)
    monkeypatch.setattr(st, "rerun", lambda: None)
    monkeypatch.setattr("wizard.render_stepper", lambda *_, **__: None)
    monkeypatch.setattr("wizard._step_summary", lambda *_: None)

    run_wizard()

    assert expected_home in button_labels
    assert expected_donate in button_labels
