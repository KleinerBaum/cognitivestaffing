from __future__ import annotations

from types import ModuleType
from typing import Any, Mapping, cast

import streamlit as st

from utils.i18n import tr
from wizard.step_layout import render_step_layout
from wizard_router import WizardContext

__all__ = ["step_skills"]


_FLOW_DEPENDENCIES: tuple[str, ...] = (
    "_get_profile_state",
    "_missing_fields_for_section",
    "_render_followups_for_step",
    "_render_review_skills_tab",
)

_get_profile_state: Any = cast(Any, None)
_missing_fields_for_section: Any = cast(Any, None)
_render_followups_for_step: Any = cast(Any, None)
_render_review_skills_tab: Any = cast(Any, None)

for _name in _FLOW_DEPENDENCIES:
    globals()[_name] = cast(Any, None)


def _get_flow_module() -> ModuleType:
    from wizard import flow as wizard_flow

    return wizard_flow


def _bind_flow_dependencies(flow: ModuleType) -> None:
    for name in _FLOW_DEPENDENCIES:
        globals()[name] = getattr(flow, name)


def _count_entries(value: object) -> int:
    return len(value) if isinstance(value, list) else 0


def _render_known(profile: Mapping[str, Any]) -> None:
    requirements_raw = profile.get("requirements")
    requirements: Mapping[str, object] = requirements_raw if isinstance(requirements_raw, Mapping) else {}
    items = [
        (tr("Pflicht-Hard-Skills", "Required hard skills"), _count_entries(requirements.get("hard_skills_required"))),
        (tr("Pflicht-Soft-Skills", "Required soft skills"), _count_entries(requirements.get("soft_skills_required"))),
        (
            tr("Tools & Technologien", "Tools & technologies"),
            _count_entries(requirements.get("tools_and_technologies")),
        ),
        (tr("Sprachen", "Languages"), _count_entries(requirements.get("languages_required"))),
    ]
    st.markdown("\n".join(f"- **{label}**: {count}" for label, count in items))


def _step_skills() -> None:
    profile = _get_profile_state()
    missing_here = _missing_fields_for_section(4)

    def _render_missing() -> None:
        _render_review_skills_tab(profile)
        _render_followups_for_step("skills", profile)

    render_step_layout(
        ("Skills & Anforderungen", "Skills & requirements"),
        (
            "Ergänze Muss-/Kann-Kriterien und konkrete Skill-Anforderungen.",
            "Complete must-/nice-to-have criteria and concrete skill requirements.",
        ),
        known_cb=lambda: _render_known(profile),
        missing_cb=_render_missing,
        missing_paths=missing_here,
        tools_cb=None,
    )


def step_skills(context: WizardContext) -> None:
    _ = context
    flow = _get_flow_module()
    _bind_flow_dependencies(flow)
    _step_skills()
