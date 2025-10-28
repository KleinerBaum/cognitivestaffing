from __future__ import annotations

import importlib

import pytest

import streamlit as st

from constants.keys import StateKeys


def test_ensure_state_initialises_wizard_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCHEMA_WIZARD_V1", "1")
    st.session_state.clear()

    # Reload schema-dependent modules to ensure the flag is honoured for cached globals.
    schema_module = importlib.import_module("core.schema")
    importlib.reload(schema_module)
    ensure_state_module = importlib.import_module("state.ensure_state")
    importlib.reload(ensure_state_module)

    ensure_state_module.ensure_state()

    profile = st.session_state[StateKeys.PROFILE]
    assert isinstance(profile, dict)
    # The RecruitingWizard schema exposes company/department/team sections.
    for key in {"company", "department", "team", "role", "tasks", "skills", "benefits", "interview_process", "summary"}:
        assert key in profile
        assert isinstance(profile[key], dict) or isinstance(profile[key], list)

    st.session_state.clear()


def test_recruiting_wizard_export_includes_new_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCHEMA_WIZARD_V1", "1")

    schema_module = importlib.import_module("core.schema")
    importlib.reload(schema_module)

    from core import schema
    from core.schema_defaults import default_recruiting_wizard
    from exports.models import RecruitingWizardExport

    payload = default_recruiting_wizard()
    export = RecruitingWizardExport.from_payload(payload)
    data = export.to_dict()

    assert "department" in data
    assert "team" in data
    assert export.canonical_keys() == schema.WIZARD_KEYS_CANONICAL
