from __future__ import annotations

from types import ModuleType
from typing import Any, cast

import streamlit as st

from constants.keys import ProfilePaths
from utils.i18n import tr
from wizard.step_layout import render_step_layout
from wizard_router import WizardContext

__all__ = ["step_interview"]


_FLOW_DEPENDENCIES: tuple[str, ...] = (
    "_get_profile_state",
    "_missing_fields_for_section",
    "_render_followups_for_step",
    "_render_review_process_tab",
    "_update_profile",
    "render_process_planner_assistant",
)

_get_profile_state: Any = cast(Any, None)
_missing_fields_for_section: Any = cast(Any, None)
_render_followups_for_step: Any = cast(Any, None)
_render_review_process_tab: Any = cast(Any, None)
_update_profile: Any = cast(Any, None)
render_process_planner_assistant: Any = cast(Any, None)

for _name in _FLOW_DEPENDENCIES:
    globals()[_name] = cast(Any, None)


def _get_flow_module() -> ModuleType:
    from wizard import flow as wizard_flow

    return wizard_flow


def _bind_flow_dependencies(flow: ModuleType) -> None:
    for name in _FLOW_DEPENDENCIES:
        globals()[name] = getattr(flow, name)


def _step_interview() -> None:
    profile = _get_profile_state()
    process = profile.setdefault("process", {})
    missing_here = _missing_fields_for_section(6)
    lang = st.session_state.get("lang", "de")

    def _render_known() -> None:
        hiring_steps = process.get("hiring_process") or []
        stakeholders = process.get("stakeholders") or []
        st.markdown(
            "\n".join(
                [
                    f"- **{tr('Prozessschritte', 'Process steps', lang=lang)}**: {len(hiring_steps)}",
                    f"- **{tr('Stakeholder', 'Stakeholders', lang=lang)}**: {len(stakeholders)}",
                ]
            )
        )

    def _render_tools() -> None:
        render_process_planner_assistant(profile, lang=lang)

    def _render_missing() -> None:
        _render_review_process_tab(profile)
        process_text = st.text_area(
            tr("Bewerbungsprozess", "Hiring process", lang=lang),
            value="\n".join(str(step) for step in process.get("hiring_process", []) if str(step).strip()),
            key="interview.hiring_process",
        )
        steps = [line.strip() for line in process_text.splitlines() if line.strip()]
        process["hiring_process"] = steps
        _update_profile(ProfilePaths.PROCESS_HIRING_PROCESS, steps)
        _render_followups_for_step("interview", profile)

    render_step_layout(
        ("Recruiting-Prozess", "Recruitment process"),
        (
            "Dokumentiere Phasen, Beteiligte und Hinweise für einen klaren Ablauf.",
            "Document stages, stakeholders, and guidance for a clear process.",
        ),
        known_cb=_render_known,
        missing_cb=_render_missing,
        missing_paths=missing_here,
        tools_cb=_render_tools,
    )


def step_interview(context: WizardContext) -> None:
    _ = context
    flow = _get_flow_module()
    _bind_flow_dependencies(flow)
    _step_interview()
