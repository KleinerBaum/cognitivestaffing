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
    parse_multiline,
    render_question_cards,
    render_summary_chips,
    render_v2_step,
    value_missing,
    profile_prefix,
)

REQUIREMENTS_PREFIX = profile_prefix(ProfilePaths.REQUIREMENTS_HARD_SKILLS_REQUIRED)

_SUMMARY_FIELDS = (
    ProfilePaths.REQUIREMENTS_HARD_SKILLS_REQUIRED,
    ProfilePaths.REQUIREMENTS_SOFT_SKILLS_REQUIRED,
    ProfilePaths.REQUIREMENTS_LANGUAGES_REQUIRED,
)


def render_requirements_board_step(context: WizardContext) -> None:
    profile = get_profile_data()
    st.header("Requirements Board")
    st.subheader(tr("Bekannt", "Known"))
    render_summary_chips(_SUMMARY_FIELDS, profile)

    st.subheader(tr("Fehlend", "Missing (Top Questions)"))
    required_paths = render_v2_step(context=context, step_key="requirements_board")
    top, optional = collect_top_questions(
        profile=profile, required_paths=required_paths, followup_prefixes=(REQUIREMENTS_PREFIX,)
    )
    render_question_cards(top)
    if optional:
        with st.expander(tr("Weitere Fragen (optional)", "More questions (optional)")):
            render_question_cards(optional)

    def _join(path: str) -> str:
        value = get_value(profile, path)
        return "\n".join(value) if isinstance(value, list) else str(value or "")

    with st.form("v2_requirements_board_form"):
        hard = st.text_area(
            str(ProfilePaths.REQUIREMENTS_HARD_SKILLS_REQUIRED),
            value=_join(str(ProfilePaths.REQUIREMENTS_HARD_SKILLS_REQUIRED)),
            height=120,
        )
        soft = st.text_area(
            str(ProfilePaths.REQUIREMENTS_SOFT_SKILLS_REQUIRED),
            value=_join(str(ProfilePaths.REQUIREMENTS_SOFT_SKILLS_REQUIRED)),
            height=100,
        )
        langs = st.text_area(
            str(ProfilePaths.REQUIREMENTS_LANGUAGES_REQUIRED),
            value=_join(str(ProfilePaths.REQUIREMENTS_LANGUAGES_REQUIRED)),
            height=100,
        )
        submitted = st.form_submit_button(tr("Änderungen speichern", "Save changes"), type="primary")
    if submitted:
        updates: dict[str, Any] = {
            str(ProfilePaths.REQUIREMENTS_HARD_SKILLS_REQUIRED): parse_multiline(hard),
            str(ProfilePaths.REQUIREMENTS_SOFT_SKILLS_REQUIRED): parse_multiline(soft),
            str(ProfilePaths.REQUIREMENTS_LANGUAGES_REQUIRED): parse_multiline(langs),
        }
        commit_profile(profile, updates, context_update=context.update_profile)
        st.success(tr("Requirements gespeichert.", "Requirements saved."))

    tools_questions = collect_followup_questions(profile=profile, followup_prefixes=(REQUIREMENTS_PREFIX,))
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


def step_requirements_board(context: WizardContext) -> None:
    render_requirements_board_step(context)
