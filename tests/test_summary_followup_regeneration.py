"""Regression tests for summary follow-up regeneration."""

from pathlib import Path
import sys

import pytest
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from constants.keys import StateKeys
from contextlib import contextmanager

from models.need_analysis import NeedAnalysisProfile

from wizard import (
    BOOLEAN_WIDGET_KEYS,
    _apply_followup_updates,
    _boolean_widget_key,
    _render_boolean_interactive_section,
    build_boolean_query,
)


pytestmark = pytest.mark.integration


def test_followup_updates_trigger_regeneration(monkeypatch) -> None:
    """Applying follow-up answers regenerates both outputs."""

    st.session_state.clear()
    st.session_state[StateKeys.JOB_AD_SELECTED_VALUES] = {}

    calls: list[str] = []

    def _fake_job_ad(*args, **kwargs) -> bool:
        calls.append("job")
        return True

    def _fake_interview(*args, **kwargs) -> bool:
        calls.append("interview")
        return True

    monkeypatch.setattr("wizard._generate_job_ad_content", _fake_job_ad)
    monkeypatch.setattr("wizard._generate_interview_guide_content", _fake_interview)

    data: dict[str, object] = {"company": {}}
    filtered_profile = {"company": {}}
    profile_payload = {
        "requirements": {},
        "responsibilities": {},
        "position": {},
        "company": {},
    }

    job_generated, interview_generated = _apply_followup_updates(
        {"company.name": " ACME "},
        data=data,
        filtered_profile=filtered_profile,
        profile_payload=profile_payload,
        target_value="Generalists",
        manual_entries=[],
        style_reference=None,
        lang="en",
        selected_fields={"company.name"},
        num_questions=5,
        warn_on_length=False,
        show_feedback=False,
    )

    assert calls == ["job", "interview"]
    assert job_generated is True
    assert interview_generated is True
    assert data["company"]["name"] == "ACME"


def test_summary_boolean_ui_uses_synonyms_and_skills(monkeypatch) -> None:
    """Boolean UI registers widgets and builds the query when data exists."""

    st.session_state.clear()

    profile = NeedAnalysisProfile.model_validate(
        {
            "position": {"job_title": "Data Engineer"},
            "requirements": {
                "hard_skills_required": ["Python"],
                "hard_skills_optional": ["SQL"],
                "soft_skills_required": [],
                "soft_skills_optional": [],
                "tools_and_technologies": [],
            },
        }
    )

    boolean_skill_terms = ["Python", "SQL"]
    boolean_title_synonyms = ["ETL Developer"]

    recorded_keys: list[str | None] = []

    monkeypatch.setattr(st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(st, "code", lambda *args, **kwargs: None)
    monkeypatch.setattr(st, "info", lambda *args, **kwargs: None)
    monkeypatch.setattr(st, "download_button", lambda *args, **kwargs: None)

    def fake_checkbox(*_args, value: bool = True, key: str | None = None, **_kwargs) -> bool:
        recorded_keys.append(key)
        return value

    @contextmanager
    def fake_expander(*_args, **_kwargs):
        yield

    monkeypatch.setattr(st, "checkbox", fake_checkbox)
    monkeypatch.setattr(st, "expander", fake_expander)

    _render_boolean_interactive_section(
        profile,
        boolean_skill_terms=boolean_skill_terms,
        boolean_title_synonyms=boolean_title_synonyms,
    )

    expected_query = build_boolean_query(
        "Data Engineer",
        boolean_skill_terms,
        include_title=True,
        title_synonyms=boolean_title_synonyms,
    )
    assert st.session_state[StateKeys.BOOLEAN_PREVIEW] == expected_query
    assert st.session_state.get(StateKeys.BOOLEAN_STR) in ("", None)

    title_key = _boolean_widget_key("boolean.title", "Data Engineer")
    synonym_keys = [_boolean_widget_key("boolean.synonym", synonym) for synonym in boolean_title_synonyms]
    skill_keys = [_boolean_widget_key("boolean.skill", skill) for skill in boolean_skill_terms]
    expected_keys = sorted(set([title_key, *synonym_keys, *skill_keys]))
    assert st.session_state[BOOLEAN_WIDGET_KEYS] == expected_keys
    assert sorted(set(recorded_keys)) == expected_keys


def test_render_followup_section_deduplicates_duplicate_fields(monkeypatch) -> None:
    """Duplicate follow-up fields should not render duplicate widget keys."""

    from wizard.flow import JobAdContext, _render_followup_section

    st.session_state.clear()
    st.session_state[StateKeys.FOLLOWUPS] = [
        {"field": "company.name", "question": "What is the company name?"},
        {"field": "company.name", "question": "Please confirm the company name."},
    ]
    st.session_state[StateKeys.WIZARD_STEP_FORM_MODE] = True

    rendered_keys: set[str] = set()

    def fake_profile_text_input(
        _field_path: str,
        _label: str,
        *,
        key: str,
        label_visibility: str = "visible",
        allow_callbacks: bool = True,
    ) -> str:
        assert label_visibility == "collapsed"
        assert allow_callbacks is False
        if key in rendered_keys:
            raise AssertionError(f"duplicate widget key: {key}")
        rendered_keys.add(key)
        st.session_state.setdefault(key, "")
        return ""

    monkeypatch.setattr("wizard.flow.profile_text_input", fake_profile_text_input)
    monkeypatch.setattr(st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(st, "form_submit_button", lambda *args, **kwargs: False)

    _render_followup_section(
        summary_data={},
        profile_payload={},
        job_context=JobAdContext(
            filtered_profile={},
            selected_fields=[],
            target_value="",
            manual_entries=[],
            style_reference="",
            style_label="",
            style_description="",
        ),
        lang="en",
    )

    assert rendered_keys == {"fu_company.name"}
