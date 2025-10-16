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
