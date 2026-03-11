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
    value_missing,
)

_SUMMARY_FIELDS = ("role.title", "role.seniority", "role.department", "role.team")
_REQUIRED = ("role.title", "role.summary")


def render_hiring_goal_step(context: WizardContext) -> None:
    profile = get_profile_data()
    st.header("Hiring Goal")
    st.subheader(tr("Bekannt", "Known"))
    render_summary_chips(_SUMMARY_FIELDS, profile)

    st.subheader(tr("Fehlend", "Missing (Top Questions)"))
    top, optional = collect_top_questions(profile=profile, required_paths=_REQUIRED, followup_prefixes=("role.",))
    render_question_cards(top)
    if optional:
        with st.expander(tr("Weitere Fragen (optional)", "More questions (optional)")):
            render_question_cards(optional)

    with st.form("v2_hiring_goal_form"):
        title = st.text_input("role.title", value=str(get_value(profile, "role.title") or ""))
        summary = st.text_area("role.summary", value=str(get_value(profile, "role.summary") or ""), height=140)
        seniority = st.text_input("role.seniority", value=str(get_value(profile, "role.seniority") or ""))
        department = st.text_input("role.department", value=str(get_value(profile, "role.department") or ""))
        team = st.text_input("role.team", value=str(get_value(profile, "role.team") or ""))
        submitted = st.form_submit_button(tr("Änderungen speichern", "Save changes"), type="primary")
    if submitted:
        updates: dict[str, Any] = {
            "role.title": title.strip(),
            "role.summary": summary.strip(),
            "role.seniority": seniority.strip(),
            "role.department": department.strip(),
            "role.team": team.strip(),
        }
        commit_profile(profile, updates, context_update=context.update_profile)
        st.success(tr("Hiring Goal gespeichert.", "Hiring goal saved."))

    tools_questions = collect_followup_questions(profile=profile, followup_prefixes=("role.",))
    if tools_questions:
        with st.expander(tr("Tools", "Tools")):
            render_question_cards(tools_questions)

    st.subheader(tr("Validieren", "Validate"))
    missing = [path for path in _REQUIRED if value_missing(get_value(profile, path))]
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


def step_hiring_goal(context: WizardContext) -> None:
    render_hiring_goal_step(context)
