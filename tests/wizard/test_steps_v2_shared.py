from __future__ import annotations

import streamlit as st

from constants.keys import StateKeys
from wizard.navigation_types import WizardContext
from wizard.steps_v2._shared import render_v2_step


def _context() -> WizardContext:
    return WizardContext(schema={}, critical_fields=())


def test_render_v2_step_prefers_explicit_missing_paths() -> None:
    st.session_state[StateKeys.WIZARD_LAST_STEP] = "intake"

    required_paths = render_v2_step(
        context=_context(),
        step_key="hiring_goal",
        missing_paths=("custom.path",),
    )

    assert required_paths == ("custom.path",)


def test_render_v2_step_reads_required_fields_from_step_registry() -> None:
    required_paths = render_v2_step(context=_context(), step_key="constraints")

    assert required_paths == ("constraints.timeline",)


def test_render_v2_step_uses_active_step_from_session_when_not_provided() -> None:
    st.session_state[StateKeys.WIZARD_LAST_STEP] = "selection"

    required_paths = render_v2_step(context=_context())

    assert required_paths == ("selection.process_steps",)
