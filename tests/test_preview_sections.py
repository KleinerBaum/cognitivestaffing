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


def test_extraction_entries_expand_iterable_summary_values() -> None:
    """List-valued summary fields should expand into multiple data points."""

    st.session_state.clear()
    context = SidebarContext(
        profile={},
        extraction_summary={"skills": {"Must-have skills": ["Python", "SQL"]}},
        skill_buckets={},
        missing_fields=set(),
        missing_by_section={},
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
        missing_by_section={},
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
        missing_by_section={},
        prefilled_sections=[],
    )

    _, step_entries = _build_initial_extraction_entries(context)

    skill_entries = step_entries["skills"]
    assert skill_entries == [("Notes", "Python, SQL")]
