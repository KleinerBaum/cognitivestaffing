from __future__ import annotations

import streamlit as st

from constants.keys import StateKeys
from core.schema_defaults import default_recruiting_wizard
from exports.models import RecruitingWizardExport
from state.ensure_state import ensure_state


def test_ensure_state_initialises_need_analysis_schema() -> None:
    st.session_state.clear()
    ensure_state()

    profile = st.session_state[StateKeys.PROFILE]
    assert isinstance(profile, dict)
    # The canonical NeedAnalysis profile exposes company/position/requirements sections.
    for key in {"company", "position", "requirements", "meta", "employment", "process", "compensation", "location", "responsibilities"}:
        assert key in profile
        assert isinstance(profile[key], dict) or isinstance(profile[key], list)

    st.session_state.clear()


def test_recruiting_wizard_export_includes_new_fields() -> None:
    from core import schema

    payload = default_recruiting_wizard()
    export = RecruitingWizardExport.from_payload(payload)
    data = export.to_dict()

    assert "department" in data
    assert "team" in data
    assert export.canonical_keys() == schema.WIZARD_KEYS_CANONICAL
