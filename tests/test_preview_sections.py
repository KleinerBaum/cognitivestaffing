from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from constants.keys import StateKeys
from core.preview import build_prefilled_sections
from models.need_analysis import NeedAnalysisProfile
from sidebar import SidebarContext, _build_initial_extraction_entries


def test_prefilled_preview_hidden_until_data_present() -> None:
    """The preview should remain hidden until real values exist."""

    st.session_state.clear()
    empty_profile = NeedAnalysisProfile().model_dump()
    st.session_state[StateKeys.PROFILE] = empty_profile
    st.session_state[StateKeys.EXTRACTION_RAW_PROFILE] = {}

    assert build_prefilled_sections() == [], "Default profile values should not trigger the preview"

    profile_with_data = NeedAnalysisProfile().model_dump()
    profile_with_data["company"]["name"] = "Acme Corp"
    st.session_state[StateKeys.PROFILE] = profile_with_data

    sections = build_prefilled_sections()

    assert sections, "Once values exist the preview should become visible"
    assert any(path == "company.name" for _, entries in sections for path, _ in entries), (
        "Stored values should appear in the preview"
    )


def test_prefilled_sections_ignore_raw_phantom_values() -> None:
    """Sidebar prefilled sections must only expose canonical profile data."""

    st.session_state.clear()
    st.session_state[StateKeys.PROFILE] = NeedAnalysisProfile().model_dump()
    st.session_state[StateKeys.EXTRACTION_RAW_PROFILE] = {
        "company": {"name": "Raw Corp"},
    }

    sections = build_prefilled_sections()

    assert sections == []


def test_extraction_entries_expand_iterable_summary_values() -> None:
    """List-valued summary fields should expand into multiple data points."""

    st.session_state.clear()
    context = SidebarContext(
        profile={},
        extraction_summary={"skills": {"Must-have skills": ["Python", "SQL"]}},
        skill_buckets={},
        missing_fields=set(),
        missing_by_step={},
        prefilled_sections=[],
    )

    _, step_entries = _build_initial_extraction_entries(context)

    skill_entries = step_entries["skills"]
    assert len(skill_entries) == 2
    assert skill_entries == [
        ("Must-have skills", "Python"),
        ("Must-have skills", "SQL"),
    ]


def test_prefilled_entries_expand_iterable_values() -> None:
    """Prefilled sequences should render each item separately."""

    st.session_state.clear()
    context = SidebarContext(
        profile={},
        extraction_summary={},
        skill_buckets={},
        missing_fields=set(),
        missing_by_step={},
        prefilled_sections=[
            (
                "Anforderungen",
                [("requirements.must_have", ["REST", "GraphQL"])],
            )
        ],
    )

    _, step_entries = _build_initial_extraction_entries(context)

    skill_entries = step_entries["skills"]
    assert len(skill_entries) == 2
    assert {label for label, _ in skill_entries} == {"Requirements → Must Have"}
    assert [value for _, value in skill_entries] == ["REST", "GraphQL"]


def test_string_values_are_not_split_into_characters() -> None:
    """Plain strings should remain single preview entries."""

    st.session_state.clear()
    context = SidebarContext(
        profile={},
        extraction_summary={"skills": {"Notes": "Python, SQL"}},
        skill_buckets={},
        missing_fields=set(),
        missing_by_step={},
        prefilled_sections=[],
    )

    _, step_entries = _build_initial_extraction_entries(context)

    skill_entries = step_entries["skills"]
    assert skill_entries == [("Notes", "Python, SQL")]


def test_resolve_active_step_key_prefers_wizard_state() -> None:
    """Sidebar should prefer the router-provided wizard step key when available."""

    st.session_state.clear()
    st.session_state["wizard"] = {"current_step_key": "landing"}

    from sidebar import _resolve_active_step_key

    assert _resolve_active_step_key() == "landing"


def test_resolve_active_step_key_falls_back_to_legacy_step_index() -> None:
    """Legacy numeric step state should map to a canonical wizard page key."""

    st.session_state.clear()
    st.session_state["_wizard_step_summary"] = "invalid"
    st.session_state[StateKeys.STEP] = 0

    from sidebar import _resolve_active_step_key

    assert _resolve_active_step_key() == "landing"


def test_sidebar_hides_step_overview_on_landing(monkeypatch) -> None:
    """Landing should suppress the sidebar step-overview block."""

    st.session_state.clear()
    st.session_state["wizard"] = {"current_step_key": "landing"}
    st.session_state[StateKeys.STEP] = 0

    from sidebar import SidebarPlan, _render_sidebar_sections

    calls = {"hero": 0, "landing": 0}

    class _Dummy:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr("sidebar._build_context", lambda: SidebarContext({}, {}, {}, set(), {}, []))
    monkeypatch.setattr("sidebar._render_hero", lambda _ctx: calls.__setitem__("hero", calls["hero"] + 1))
    monkeypatch.setattr(
        "sidebar._render_landing_next_steps_compact",
        lambda: calls.__setitem__("landing", calls["landing"] + 1),
    )
    monkeypatch.setattr("sidebar._render_settings", lambda: None)
    monkeypatch.setattr("sidebar._render_salary_expectation", lambda _profile: None)
    monkeypatch.setattr("sidebar._render_help_section", lambda: None)
    monkeypatch.setattr("sidebar._render_step_context", lambda _ctx: None)
    monkeypatch.setattr("sidebar._is_sidebar_stepper_enabled", lambda: False)
    monkeypatch.setattr(st, "divider", lambda: None)

    plan = SidebarPlan(branding=_Dummy(), settings=_Dummy(), body=_Dummy())
    _render_sidebar_sections(plan, logo_asset=None, logo_data_uri=None)

    assert calls["hero"] == 0
    assert calls["landing"] == 1


def test_extraction_entries_mark_raw_on_llm_error() -> None:
    """Extraction summary entries should be labeled as raw when LLM extraction fails."""

    st.session_state.clear()
    st.session_state[StateKeys.PROFILE_METADATA] = {"llm_errors": {"extraction": "boom"}}
    context = SidebarContext(
        profile={},
        extraction_summary={"Status": "⚠️ AI extraction failed"},
        skill_buckets={},
        missing_fields=set(),
        missing_by_step={},
        prefilled_sections=[],
    )

    _, step_entries = _build_initial_extraction_entries(context)

    assert step_entries["jobad"] == [("Status (raw)", "⚠️ AI extraction failed")]
