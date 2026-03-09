from __future__ import annotations

from types import ModuleType
from typing import Any, cast

import streamlit as st

from constants.keys import ProfilePaths
from utils.i18n import tr
from wizard.step_layout import render_step_layout
from wizard_router import WizardContext

__all__ = ["step_benefits"]


_FLOW_DEPENDENCIES: tuple[str, ...] = (
    "_get_profile_state",
    "_missing_fields_for_section",
    "_render_followups_for_step",
    "_update_profile",
    "render_compensation_assistant",
)

_get_profile_state: Any = cast(Any, None)
_missing_fields_for_section: Any = cast(Any, None)
_render_followups_for_step: Any = cast(Any, None)
_update_profile: Any = cast(Any, None)
render_compensation_assistant: Any = cast(Any, None)

for _name in _FLOW_DEPENDENCIES:
    globals()[_name] = cast(Any, None)


def _get_flow_module() -> ModuleType:
    from wizard import flow as wizard_flow

    return wizard_flow


def _bind_flow_dependencies(flow: ModuleType) -> None:
    for name in _FLOW_DEPENDENCIES:
        globals()[name] = getattr(flow, name)


def _step_benefits() -> None:
    profile = _get_profile_state()
    compensation = profile.setdefault("compensation", {})
    missing_here = _missing_fields_for_section(5)

    def _render_known() -> None:
        salary_min = compensation.get("salary_min")
        salary_max = compensation.get("salary_max")
        currency = compensation.get("currency") or "EUR"
        benefits_count = len(list(compensation.get("benefits") or []))
        st.markdown(
            "\n".join(
                [
                    f"- **{tr('Gehalt', 'Salary')}**: {salary_min or '—'} – {salary_max or '—'} {currency}",
                    f"- **{tr('Benefits', 'Benefits')}**: {benefits_count}",
                ]
            )
        )

    def _render_tools() -> None:
        render_compensation_assistant(profile)

    def _render_missing() -> None:
        col_min, col_max, col_currency = st.columns(3)
        salary_min = int(
            col_min.number_input(
                tr("Gehalt min.", "Salary min."),
                value=int(compensation.get("salary_min") or 0),
                min_value=0,
                step=1_000,
                key="benefits.salary_min",
            )
        )
        salary_max = int(
            col_max.number_input(
                tr("Gehalt max.", "Salary max."),
                value=int(compensation.get("salary_max") or 0),
                min_value=0,
                step=1_000,
                key="benefits.salary_max",
            )
        )
        currency = col_currency.text_input(
            tr("Währung", "Currency"),
            value=str(compensation.get("currency") or "EUR"),
            key="benefits.currency",
        ).strip()

        benefits_text = st.text_area(
            tr("Benefits (eine Zeile pro Eintrag)", "Benefits (one line per item)"),
            value="\n".join(str(item) for item in compensation.get("benefits", []) if str(item).strip()),
            key="benefits.items",
        )
        benefit_items = [line.strip() for line in benefits_text.splitlines() if line.strip()]

        compensation["salary_min"] = salary_min
        compensation["salary_max"] = salary_max
        compensation["currency"] = currency
        compensation["benefits"] = benefit_items

        _update_profile(ProfilePaths.COMPENSATION_SALARY_MIN, salary_min)
        _update_profile(ProfilePaths.COMPENSATION_SALARY_MAX, salary_max)
        _update_profile(ProfilePaths.COMPENSATION_CURRENCY, currency)
        _update_profile(ProfilePaths.COMPENSATION_BENEFITS, benefit_items)
        _render_followups_for_step("benefits", profile)

    render_step_layout(
        ("Benefits", "Benefits"),
        (
            "Pflege Gehaltsband und Zusatzleistungen in kompakter Form.",
            "Maintain salary band and benefits in a compact form.",
        ),
        known_cb=_render_known,
        missing_cb=_render_missing,
        missing_paths=missing_here,
        tools_cb=_render_tools,
    )


def step_benefits(context: WizardContext) -> None:
    _ = context
    flow = _get_flow_module()
    _bind_flow_dependencies(flow)
    _step_benefits()
