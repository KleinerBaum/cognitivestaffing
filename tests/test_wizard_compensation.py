"""Tests for the compensation wizard step."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import streamlit as st

from constants.keys import StateKeys
from wizard import _generate_local_benefits, _step_compensation


pytestmark = pytest.mark.integration


class StopWizard(RuntimeError):
    """Sentinel exception to abort the compensation step during tests."""


def test_generate_local_benefits_collapses_case_variants(monkeypatch: pytest.MonkeyPatch) -> None:
    """Duplicate local suggestions differing only by case collapse into one entry."""

    profile = {"compensation": {"benefits": []}, "location": {"country": "", "city": ""}}

    monkeypatch.setattr("wizard._LOCAL_BENEFIT_FALLBACKS", [("City Perk", "City Perk"), ("city perk", "city perk")])
    monkeypatch.setattr("wizard._LOCAL_BENEFIT_COUNTRY_PRESETS", {})

    suggestions = _generate_local_benefits(profile, lang="en")

    assert suggestions == ["City Perk"], "case variants should be merged into a single suggestion"


def test_step_compensation_normalizes_benefit_options(monkeypatch: pytest.MonkeyPatch) -> None:
    """Benefit options and values are normalised case-insensitively before rendering."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state[StateKeys.BENEFIT_SUGGESTION_HINTS] = []
    st.session_state[StateKeys.LOCAL_BENEFIT_CONTEXT] = None
    st.session_state[StateKeys.LOCAL_BENEFIT_SUGGESTIONS] = []
    st.session_state[StateKeys.BENEFIT_SUGGESTIONS] = {
        "_lang": "en",
        "llm": ["Health Insurance", "health insurance"],
        "fallback": ["Gym membership", "gym membership"],
    }
    st.session_state[StateKeys.PROFILE] = {
        "position": {"job_title": "Data Scientist"},
        "company": {"industry": "Tech"},
        "location": {"country": "Germany", "city": "Berlin"},
        "compensation": {
            "salary_min": 0,
            "salary_max": 0,
            "salary_provided": False,
            "currency": "EUR",
            "period": "year",
            "benefits": ["Gym Membership", "gym membership"],
            "variable_pay": False,
            "equity_offered": False,
        },
    }

    monkeypatch.setattr("wizard._inject_salary_slider_styles", lambda: None)
    monkeypatch.setattr("wizard._build_profile_context", lambda _profile: {})
    monkeypatch.setattr("wizard.flow.render_compensation_assistant", lambda *_args, **_kwargs: None)

    def fake_format_dynamic_message(*, default, context, variants):  # type: ignore[override]
        lang = st.session_state.get("lang", "de")
        return default[0] if lang == "de" else default[1]

    monkeypatch.setattr("wizard._format_dynamic_message", fake_format_dynamic_message)
    monkeypatch.setattr(
        "wizard._derive_salary_range_defaults",
        lambda *_args, **_kwargs: SimpleNamespace(minimum=0, maximum=0, currency="EUR"),
    )
    monkeypatch.setattr("wizard.get_static_benefit_shortlist", lambda lang, industry: ["Gym membership"])

    class FakeColumn:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def selectbox(self, _label, *, options, index=0, **_kwargs):
            return options[index]

        def text_input(self, _label, value="", **_kwargs):
            return value

        def toggle(self, _label, value=False, **_kwargs):
            return value

        def number_input(self, _label, *, value=0.0, **_kwargs):
            return value

        def button(self, *_args, **_kwargs):
            return False

    class FakeExpander:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_columns(spec, **_kwargs):
        count = spec if isinstance(spec, int) else len(spec)
        return tuple(FakeColumn() for _ in range(count))

    monkeypatch.setattr(st, "subheader", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "info", lambda *_, **__: None)
    monkeypatch.setattr(st, "warning", lambda *_, **__: None)
    monkeypatch.setattr(st, "button", lambda *_, **__: False)
    monkeypatch.setattr(st, "slider", lambda *_, **__: (0, 0))
    monkeypatch.setattr(st, "expander", lambda *_, **__: FakeExpander())
    monkeypatch.setattr(st, "columns", fake_columns)
    monkeypatch.setattr(st, "rerun", lambda: None)

    captured: dict[str, list[str]] = {}

    def fake_chip_multiselect(label, *, options, values, **kwargs):
        if "Benefits" in label:
            captured["options"] = options
            captured["values"] = values
            return ["Gym Membership", "Health Insurance"]
        return values

    monkeypatch.setattr("wizard.chip_multiselect", fake_chip_multiselect)
    monkeypatch.setattr("wizard.flow.group_chip_options_by_label", lambda entries: [("", list(entries))])
    monkeypatch.setattr("wizard.flow.render_chip_button_grid", lambda values, **_: None)
    monkeypatch.setattr(
        "wizard._render_followups_for_section",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(StopWizard()),
    )

    with pytest.raises(StopWizard):
        _step_compensation()

    assert captured["options"] == [
        "Gym Membership",
        "Health Insurance",
    ], "available options should deduplicate case-insensitively"
    assert captured["values"] == [
        "Gym Membership",
    ], "existing benefits should be normalised before rendering"
    profile = st.session_state[StateKeys.PROFILE]
    assert profile["compensation"]["benefits"] == [
        "Gym Membership",
        "Health Insurance",
    ], "selected benefits should be stored without duplicates"
    state = st.session_state[StateKeys.BENEFIT_SUGGESTIONS]
    assert state["llm"] == [
        "Health Insurance",
    ], "LLM suggestions should be normalised"
    assert state["fallback"] == [
        "Gym membership",
    ], "Fallback suggestions should be normalised"


def test_compensation_benefits_chip_multiselect_uses_distinct_key_suffixes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Step and summary benefits keep the same state key with different widget suffixes."""

    from wizard import _summary_compensation

    st.session_state.clear()
    st.session_state["lang"] = "en"
    st.session_state[StateKeys.BENEFIT_SUGGESTION_HINTS] = []
    st.session_state[StateKeys.LOCAL_BENEFIT_CONTEXT] = None
    st.session_state[StateKeys.LOCAL_BENEFIT_SUGGESTIONS] = []
    st.session_state[StateKeys.BENEFIT_SUGGESTIONS] = {"_lang": "en", "llm": [], "fallback": []}
    st.session_state[StateKeys.PROFILE] = {
        "position": {"job_title": "Data Scientist"},
        "company": {"industry": "Tech"},
        "location": {"country": "Germany", "city": "Berlin"},
        "compensation": {
            "salary_min": 0,
            "salary_max": 0,
            "salary_provided": False,
            "currency": "EUR",
            "period": "year",
            "benefits": ["Gym Membership"],
            "variable_pay": False,
            "equity_offered": False,
        },
    }

    monkeypatch.setattr("wizard._inject_salary_slider_styles", lambda: None)
    monkeypatch.setattr("wizard._build_profile_context", lambda _profile: {})
    monkeypatch.setattr("wizard.flow.render_compensation_assistant", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("wizard._format_dynamic_message", lambda **kwargs: kwargs["default"][1])
    monkeypatch.setattr(
        "wizard._derive_salary_range_defaults",
        lambda *_args, **_kwargs: SimpleNamespace(minimum=0, maximum=0, currency="EUR"),
    )
    monkeypatch.setattr("wizard.get_static_benefit_shortlist", lambda lang, industry: ["Gym Membership"])
    monkeypatch.setattr(
        "wizard.flow.resolve_sidebar_benefits",
        lambda **_kwargs: SimpleNamespace(
            llm_suggestions=[],
            fallback_suggestions=[],
            suggestions=[],
            source="fallback",
        ),
    )
    monkeypatch.setattr("wizard._update_profile", lambda *_, **__: None)

    class FakeColumn:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def selectbox(self, _label, *, options, index=0, **_kwargs):
            return options[index]

        def text_input(self, _label, value="", **_kwargs):
            return value

        def toggle(self, _label, value=False, **_kwargs):
            return value

        def number_input(self, _label, *, value=0.0, **_kwargs):
            return value

        def button(self, *_args, **_kwargs):
            return False

    class FakeExpander:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_columns(spec, **_kwargs):
        count = spec if isinstance(spec, int) else len(spec)
        return tuple(FakeColumn() for _ in range(count))

    monkeypatch.setattr(st, "subheader", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", lambda *_, **__: None)
    monkeypatch.setattr(st, "markdown", lambda *_, **__: None)
    monkeypatch.setattr(st, "info", lambda *_, **__: None)
    monkeypatch.setattr(st, "warning", lambda *_, **__: None)
    monkeypatch.setattr(st, "button", lambda *_, **__: False)
    monkeypatch.setattr(st, "slider", lambda *_, **__: (0, 0))
    monkeypatch.setattr(st, "expander", lambda *_, **__: FakeExpander())
    monkeypatch.setattr(st, "columns", fake_columns)
    monkeypatch.setattr(st, "rerun", lambda: None)

    seen_widget_keys: set[str] = set()
    benefit_calls: list[tuple[str | None, str | None]] = []

    def fake_chip_multiselect(label, *, options, values, key_suffix=None, state_key=None, **kwargs):
        slug_parts: list[str] = []
        canonical_root = str(state_key).strip() if state_key else ""
        if canonical_root:
            slug_parts.append(canonical_root)
        if key_suffix:
            slug_parts.append(str(key_suffix).strip())
        widget_key = f"ms_{'.'.join(slug_parts)}"
        assert widget_key not in seen_widget_keys, f"duplicate widget key created: {widget_key}"
        seen_widget_keys.add(widget_key)

        if state_key == "compensation.benefits":
            benefit_calls.append((state_key, key_suffix))
        if "Benefits" in label:
            return ["Gym Membership"]
        return values

    monkeypatch.setattr("wizard.flow.chip_multiselect", fake_chip_multiselect)
    monkeypatch.setattr("wizard.flow._render_followups_for_section", lambda *_args, **_kwargs: None)

    _step_compensation()
    _summary_compensation()

    assert benefit_calls == [
        ("compensation.benefits", "step_compensation"),
        ("compensation.benefits", "summary_compensation"),
    ]
