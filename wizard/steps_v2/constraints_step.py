from __future__ import annotations

from typing import Any

import streamlit as st

from utils.i18n import tr
from wizard.navigation_types import WizardContext

from ._shared import (
    collect_followup_questions,
    collect_top_questions,
    commit_profile,
    get_profile_data,
    get_value,
    render_question_cards,
    render_summary_chips,
    render_v2_step,
    value_missing,
)

_SUMMARY_FIELDS = ("constraints.salary_min", "constraints.salary_max", "constraints.timeline")


def render_constraints_step(context: WizardContext) -> None:
    profile = get_profile_data()
    st.header("Constraints")
    st.subheader(tr("Bekannt", "Known"))
    render_summary_chips(_SUMMARY_FIELDS, profile)

    st.subheader(tr("Fehlend", "Missing (Top Questions)"))
    required_paths = render_v2_step(context=context, step_key="constraints")
    top, optional = collect_top_questions(
        profile=profile, required_paths=required_paths, followup_prefixes=("constraints.",)
    )
    render_question_cards(top)
    if optional:
        with st.expander(tr("Weitere Fragen (optional)", "More questions (optional)")):
            render_question_cards(optional)

    salary_min_raw = get_value(profile, "constraints.salary_min")
    salary_max_raw = get_value(profile, "constraints.salary_max")
    with st.form("v2_constraints_form"):
        timeline = st.text_input("constraints.timeline", value=str(get_value(profile, "constraints.timeline") or ""))
        salary_min = st.number_input(
            "constraints.salary_min", value=float(salary_min_raw or 0.0), min_value=0.0, step=1000.0
        )
        salary_max = st.number_input(
            "constraints.salary_max", value=float(salary_max_raw or 0.0), min_value=0.0, step=1000.0
        )
        submitted = st.form_submit_button(tr("Änderungen speichern", "Save changes"), type="primary")
    if submitted:
        updates: dict[str, Any] = {
            "constraints.timeline": timeline.strip(),
            "constraints.salary_min": int(salary_min) if salary_min else None,
            "constraints.salary_max": int(salary_max) if salary_max else None,
        }
        commit_profile(profile, updates, context_update=context.update_profile)
        st.success(tr("Constraints gespeichert.", "Constraints saved."))

    tools_questions = collect_followup_questions(profile=profile, followup_prefixes=("constraints.",))
    if tools_questions:
        with st.expander(tr("Tools", "Tools")):
            render_question_cards(tools_questions)

    st.subheader(tr("Validieren", "Validate"))
    missing = [path for path in required_paths if value_missing(get_value(profile, path))]
    st.warning("\n".join(f"- `{path}`" for path in missing)) if missing else st.success(
        tr("Pflichtfelder vollständig.", "Required fields complete.")
    )
    st.subheader("Nav")
    st.caption(
        tr(
            "Navigation über die Wizard-Buttons unten (Zurück/Weiter).",
            "Use wizard navigation buttons below (Back/Next).",
        )
    )


def step_constraints(context: WizardContext) -> None:
    render_constraints_step(context)
