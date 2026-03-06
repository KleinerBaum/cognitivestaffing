from __future__ import annotations

from types import ModuleType
from typing import Any, Mapping, cast

import streamlit as st

from utils.i18n import tr
from wizard.step_layout import render_step_layout
from wizard_router import WizardContext

__all__ = ["step_role_tasks"]


_FLOW_DEPENDENCIES: tuple[str, ...] = (
    "_get_profile_state",
    "_missing_fields_for_section",
    "_render_followups_for_step",
    "_render_review_requirements_tab",
)

_get_profile_state: Any = cast(Any, None)
_missing_fields_for_section: Any = cast(Any, None)
_render_followups_for_step: Any = cast(Any, None)
_render_review_requirements_tab: Any = cast(Any, None)

for _name in _FLOW_DEPENDENCIES:
    globals()[_name] = cast(Any, None)


def _get_flow_module() -> ModuleType:
    from wizard import flow as wizard_flow

    return wizard_flow


def _bind_flow_dependencies(flow: ModuleType) -> None:
    for name in _FLOW_DEPENDENCIES:
        globals()[name] = getattr(flow, name)


def _render_known(profile: Mapping[str, Any]) -> None:
    responsibilities = profile.get("responsibilities") if isinstance(profile.get("responsibilities"), Mapping) else {}
    requirements = profile.get("requirements") if isinstance(profile.get("requirements"), Mapping) else {}
    items = [
        (tr("Aufgaben", "Responsibilities"), len(list(responsibilities.get("items") or []))),
        (tr("Pflicht-Hard-Skills", "Required hard skills"), len(list(requirements.get("hard_skills_required") or []))),
        (tr("Pflicht-Soft-Skills", "Required soft skills"), len(list(requirements.get("soft_skills_required") or []))),
        (
            tr("Tools & Technologien", "Tools & technologies"),
            len(list(requirements.get("tools_and_technologies") or [])),
        ),
    ]
    st.markdown("\n".join(f"- **{label}**: {count}" for label, count in items))


def _step_role_tasks() -> None:
    profile = _get_profile_state()
    missing_here = _missing_fields_for_section(3)

    def _render_missing() -> None:
        _render_review_requirements_tab(profile)
        _render_followups_for_step("role_tasks", profile)

    render_step_layout(
        ("Aufgaben & Skills", "Tasks & Skills"),
        (
            "Ergänze die Kernaufgaben sowie Muss-/Kann-Skills in strukturierter Form.",
            "Complete core responsibilities and must-/nice-to-have skills in a structured format.",
        ),
        known_cb=lambda: _render_known(profile),
        missing_cb=_render_missing,
        missing_paths=missing_here,
        tools_cb=None,
    )


def step_role_tasks(context: WizardContext) -> None:
    _ = context
    flow = _get_flow_module()
    _bind_flow_dependencies(flow)
    _step_role_tasks()
