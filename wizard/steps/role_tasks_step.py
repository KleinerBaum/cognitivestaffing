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
    "_render_review_role_tasks_tab",
)

_get_profile_state: Any = cast(Any, None)
_missing_fields_for_section: Any = cast(Any, None)
_render_followups_for_step: Any = cast(Any, None)
_render_review_role_tasks_tab: Any = cast(Any, None)

for _name in _FLOW_DEPENDENCIES:
    globals()[_name] = cast(Any, None)


def _get_flow_module() -> ModuleType:
    from wizard import flow as wizard_flow

    return wizard_flow


def _bind_flow_dependencies(flow: ModuleType) -> None:
    for name in _FLOW_DEPENDENCIES:
        globals()[name] = getattr(flow, name)


def _render_known(profile: Mapping[str, Any]) -> None:
    responsibilities_raw = profile.get("responsibilities")
    responsibilities: Mapping[str, object] = responsibilities_raw if isinstance(responsibilities_raw, Mapping) else {}
    items_raw = responsibilities.get("items")
    item_count = len(items_raw) if isinstance(items_raw, list) else 0
    st.markdown(f"- **{tr('Aufgaben', 'Responsibilities')}**: {item_count}")


def _step_role_tasks() -> None:
    profile = _get_profile_state()
    missing_here = _missing_fields_for_section(3)

    def _render_missing() -> None:
        _render_review_role_tasks_tab(profile)
        _render_followups_for_step("role_tasks", profile)

    render_step_layout(
        ("Aufgaben", "Tasks"),
        (
            "Ergänze die Kernaufgaben in strukturierter Form.",
            "Complete core responsibilities in a structured format.",
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
