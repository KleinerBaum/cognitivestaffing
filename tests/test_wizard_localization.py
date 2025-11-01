"""Localization regression tests for wizard labels."""

from __future__ import annotations

import inspect
from pathlib import Path
import sys

import pytest
import streamlit as st

import components.requirements_insights as requirements_insights

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from components.requirements_insights import (
    SkillMarketRecord,
    _render_summary,
    build_availability_chart_spec,
    build_salary_chart_spec,
    render_skill_market_insights,
)


pytestmark = pytest.mark.integration
from constants.keys import StateKeys
from pages import WIZARD_PAGES
from wizard import STEP_RENDERERS, _step_compensation, _summary_compensation, run_wizard
from utils import i18n


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
        "requirements": {
            "hard_skills_required": [],
            "hard_skills_optional": [],
            "soft_skills_required": [],
            "soft_skills_optional": [],
            "tools_and_technologies": [],
            "languages_required": [],
            "languages_optional": [],
        },
        "employment": {
            "employment_type": "",
            "work_model": "",
        },
        "process": {
            "steps": [],
        },
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

    def multiselect(self, label: str, *, options, default=None, **kwargs):  # pragma: no cover
        if default is not None:
            return list(default)
        return list(options)

    def toggle(self, label: str, *, value=False, **kwargs):
        self._toggle_recorder.append(label)
        return value

    def text_input(self, label: str, *, value="", **kwargs):  # pragma: no cover - passthrough
        return value

    def number_input(self, label: str, *, value=0, **kwargs):  # pragma: no cover - passthrough
        return value

    def text_area(self, label: str, *, value="", **kwargs):  # pragma: no cover - passthrough
        return value

    def date_input(self, label: str, *, value=None, **kwargs):  # pragma: no cover - passthrough
        return value

    def markdown(self, *_args, **_kwargs) -> None:  # pragma: no cover - passthrough
        return None

    def empty(self) -> None:  # pragma: no cover - passthrough
        return None


def _patch_columns(monkeypatch: pytest.MonkeyPatch, toggle_recorder: list[str]) -> None:
    def fake_columns(spec, *_, **__):
        count = spec if isinstance(spec, int) else len(spec)
        return tuple(_Column(toggle_recorder) for _ in range(count))

    monkeypatch.setattr(st, "columns", fake_columns)


def _patch_common_streamlit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(st, "subheader", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "button", lambda *_, **__: False)
    monkeypatch.setattr(st, "slider", lambda *_, value, **__: value)

    def _fake_text_input(*_, key=None, value="", **__):
        if key is not None and key not in st.session_state:
            st.session_state[key] = value
        return st.session_state.get(key, value)

    monkeypatch.setattr(st, "text_input", _fake_text_input)
    monkeypatch.setattr(st, "multiselect", lambda *_, default, **__: default)


def _assert_translation_pair(pair: tuple[str, str]) -> None:
    de_text, en_text = pair
    assert de_text.strip(), f"Missing German translation for {pair!r}"
    assert en_text.strip(), f"Missing English translation for {pair!r}"


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
    profile = _base_profile()
    profile.setdefault("requirements", {})
    st.session_state[StateKeys.PROFILE] = profile
    st.session_state[StateKeys.BENEFIT_SUGGESTIONS] = {"llm": [], "fallback": []}
    st.session_state["lang"] = lang

    _patch_columns(monkeypatch, toggle_labels)
    _patch_common_streamlit(monkeypatch)

    def _recording_chip(label, *, options, values, **__):
        chip_labels.append(label)
        return values

    monkeypatch.setattr("wizard.runner.chip_multiselect", _recording_chip)
    monkeypatch.setattr("wizard.chip_multiselect", _recording_chip)

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

    def _recording_chip(label, *, options, values, **__):
        chip_labels.append(label)
        return values

    monkeypatch.setattr("wizard.runner.chip_multiselect", _recording_chip)
    monkeypatch.setattr("wizard.chip_multiselect", _recording_chip)
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

    def fake_columns(spec, *_, **__):
        count = spec if isinstance(spec, int) else len(spec)
        return tuple(_Column([]) for _ in range(count))

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


def test_wizard_pages_have_translations() -> None:
    keys: set[str] = set()
    for page in WIZARD_PAGES:
        assert page.key not in keys, f"Duplicate wizard page key: {page.key}"
        keys.add(page.key)
        _assert_translation_pair(page.label)
        _assert_translation_pair(page.panel_header)
        _assert_translation_pair(page.panel_subheader)
        for variant in page.panel_intro_variants:
            _assert_translation_pair(variant)
        for lang in ("de", "en"):
            assert page.label_for(lang).strip()
            assert page.header_for(lang).strip()
            assert page.subheader_for(lang).strip()
            for intro in page.intro_variants_for(lang):
                assert intro.strip()


def test_skill_market_charts_use_translation_labels() -> None:
    record = SkillMarketRecord(
        skill="Python",
        normalized_skill="python",
        salary_delta_pct=5.0,
        availability_index=42.0,
        has_benchmark=True,
    )

    salary_spec_en = build_salary_chart_spec([record], lang="en")
    assert salary_spec_en["encoding"]["x"]["axis"]["title"] == "Salary impact (%)"
    assert salary_spec_en["encoding"]["tooltip"][1]["title"] == "Salary impact"

    salary_spec_de = build_salary_chart_spec([record], lang="de")
    assert salary_spec_de["encoding"]["x"]["axis"]["title"] == "Gehaltsimpact (%)"
    assert salary_spec_de["encoding"]["tooltip"][1]["title"] == "Gehaltsimpact"

    availability_spec_en = build_availability_chart_spec([record], lang="en")
    assert availability_spec_en["encoding"]["x"]["axis"]["title"] == "Talent availability (0–100)"
    assert availability_spec_en["encoding"]["tooltip"][1]["title"] == "Talent availability"

    availability_spec_de = build_availability_chart_spec([record], lang="de")
    assert availability_spec_de["encoding"]["x"]["axis"]["title"] == "Talent-Verfügbarkeit (0–100)"
    assert availability_spec_de["encoding"]["tooltip"][1]["title"] == "Talent-Verfügbarkeit"


def test_skill_market_summary_uses_translation_pairs(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []
    monkeypatch.setattr(st, "caption", lambda value, *_, **__: captured.append(value))

    _render_summary(
        [
            SkillMarketRecord(
                skill="Python",
                normalized_skill="python",
                salary_delta_pct=5.0,
                availability_index=42.0,
                has_benchmark=True,
            )
        ],
        segment_label="Engineering",
        lang="en",
        location=None,
    )

    assert captured[0] == "Engineering: Salary impact +5.0% · Availability 42/100."


def test_skill_market_summary_fallback_translations(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []
    monkeypatch.setattr(st, "caption", lambda value, *_, **__: captured.append(value))

    _render_summary(
        [
            SkillMarketRecord(
                skill="Python",
                normalized_skill="python",
                salary_delta_pct=0.0,
                availability_index=50.0,
                has_benchmark=False,
            )
        ],
        segment_label="Engineering",
        lang="de",
        location=None,
    )

    assert captured[0] == "Engineering: Keine Auswertung verfügbar – bitte Skills erfassen."


class _StopAfterMultiselect(Exception):
    """Internal sentinel exception to halt rendering after capturing the label."""


def test_skill_market_multiselect_label_localized(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_label: list[str] = []

    st.session_state.clear()
    st.session_state["lang"] = "en"

    def fake_multiselect(label, *_, **__):
        captured_label.append(label)
        raise _StopAfterMultiselect

    monkeypatch.setattr(st, "multiselect", fake_multiselect)

    with pytest.raises(_StopAfterMultiselect):
        render_skill_market_insights(["Python"], segment_label="Engineering")

    assert captured_label == ["Select skill"]


def test_wizard_pages_have_step_renderers() -> None:
    page_keys = {page.key for page in WIZARD_PAGES}
    renderer_keys = set(STEP_RENDERERS.keys())
    missing = sorted(page_keys - renderer_keys)
    assert not missing, f"Missing step renderers for: {missing}"


def test_skill_market_translation_keys_are_used() -> None:
    source = inspect.getsource(requirements_insights)
    constant_names = [
        name for name, value in vars(i18n).items() if name.startswith("SKILL_MARKET_") and isinstance(value, tuple)
    ]
    missing = [name for name in constant_names if name not in source]
    assert not missing, f"Unused translation constants: {missing}"
