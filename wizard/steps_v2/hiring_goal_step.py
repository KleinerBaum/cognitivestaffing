from __future__ import annotations

from typing import Any

import streamlit as st

from constants.keys import ProfilePaths
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
    profile_prefix,
)

ROLE_PREFIX = profile_prefix(ProfilePaths.ROLE_TITLE)

_SUMMARY_FIELDS = (
    ProfilePaths.ROLE_TITLE,
    ProfilePaths.ROLE_SENIORITY,
    ProfilePaths.ROLE_DEPARTMENT,
    ProfilePaths.ROLE_TEAM,
)


def render_hiring_goal_step(context: WizardContext) -> None:
    profile = get_profile_data()
    st.header("Hiring Goal")
    st.subheader(tr("Bekannt", "Known"))
    render_summary_chips(_SUMMARY_FIELDS, profile)

    st.subheader(tr("Fehlend", "Missing (Top Questions)"))
    required_paths = render_v2_step(context=context, step_key="hiring_goal")
    top, optional = collect_top_questions(
        profile=profile, required_paths=required_paths, followup_prefixes=(ROLE_PREFIX,)
    )
    render_question_cards(top)
    if optional:
        with st.expander(tr("Weitere Fragen (optional)", "More questions (optional)")):
            render_question_cards(optional)

    with st.form("v2_hiring_goal_form"):
        title = st.text_input(
            str(ProfilePaths.ROLE_TITLE), value=str(get_value(profile, str(ProfilePaths.ROLE_TITLE)) or "")
        )
        summary = st.text_area(
            str(ProfilePaths.ROLE_SUMMARY),
            value=str(get_value(profile, str(ProfilePaths.ROLE_SUMMARY)) or ""),
            height=140,
        )
        seniority = st.text_input(
            str(ProfilePaths.ROLE_SENIORITY), value=str(get_value(profile, str(ProfilePaths.ROLE_SENIORITY)) or "")
        )
        department = st.text_input(
            str(ProfilePaths.ROLE_DEPARTMENT), value=str(get_value(profile, str(ProfilePaths.ROLE_DEPARTMENT)) or "")
        )
        team = st.text_input(
            str(ProfilePaths.ROLE_TEAM), value=str(get_value(profile, str(ProfilePaths.ROLE_TEAM)) or "")
        )
        submitted = st.form_submit_button(tr("Änderungen speichern", "Save changes"), type="primary")
    if submitted:
        updates: dict[str, Any] = {
            str(ProfilePaths.ROLE_TITLE): title.strip(),
            str(ProfilePaths.ROLE_SUMMARY): summary.strip(),
            str(ProfilePaths.ROLE_SENIORITY): seniority.strip(),
            str(ProfilePaths.ROLE_DEPARTMENT): department.strip(),
            str(ProfilePaths.ROLE_TEAM): team.strip(),
        }
        commit_profile(profile, updates, context_update=context.update_profile)
        st.success(tr("Hiring Goal gespeichert.", "Hiring goal saved."))

    tools_questions = collect_followup_questions(profile=profile, followup_prefixes=(ROLE_PREFIX,))
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


def step_hiring_goal(context: WizardContext) -> None:
    render_hiring_goal_step(context)
