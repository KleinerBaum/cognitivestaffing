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
    profile_prefix,
)

_SUMMARY_FIELDS = (ProfilePaths.OPEN_DECISIONS, ProfilePaths.WARNINGS)
REVIEW_PREFIXES = (
    profile_prefix(ProfilePaths.OPEN_DECISIONS).removesuffix("."),
    profile_prefix(ProfilePaths.WARNINGS).removesuffix("."),
)


def render_review_step(context: WizardContext) -> None:
    profile = get_profile_data()
    st.header("Review")
    st.subheader(tr("Bekannt", "Known"))
    render_summary_chips(_SUMMARY_FIELDS, profile)

    st.subheader(tr("Fehlend", "Missing (Top Questions)"))
    top, optional = collect_top_questions(profile=profile, required_paths=(), followup_prefixes=REVIEW_PREFIXES)
    if top:
        render_question_cards(top)
    else:
        st.info(tr("Keine offenen Pflichtfragen im Review-Schritt.", "No required open questions in review step."))
    if optional:
        with st.expander(tr("Weitere Fragen (optional)", "More questions (optional)")):
            render_question_cards(optional)

    open_decisions_raw = get_value(profile, str(ProfilePaths.OPEN_DECISIONS))
    warnings_raw = get_value(profile, str(ProfilePaths.WARNINGS))
    with st.form("v2_review_form"):
        open_decisions = st.text_area(
            str(ProfilePaths.OPEN_DECISIONS),
            value="\n".join(open_decisions_raw)
            if isinstance(open_decisions_raw, list)
            else str(open_decisions_raw or ""),
            height=120,
        )
        warnings = st.text_area(
            str(ProfilePaths.WARNINGS),
            value="\n".join(warnings_raw) if isinstance(warnings_raw, list) else str(warnings_raw or ""),
            height=120,
        )
        submitted = st.form_submit_button(tr("Änderungen speichern", "Save changes"), type="primary")
    if submitted:
        updates: dict[str, Any] = {
            str(ProfilePaths.OPEN_DECISIONS): parse_multiline(open_decisions),
            str(ProfilePaths.WARNINGS): parse_multiline(warnings),
        }
        commit_profile(profile, updates, context_update=context.update_profile)
        st.success(tr("Review gespeichert.", "Review saved."))

    tools_questions = collect_followup_questions(profile=profile, followup_prefixes=REVIEW_PREFIXES)
    if tools_questions:
        with st.expander(tr("Tools", "Tools")):
            render_question_cards(tools_questions)

    st.subheader(tr("Validieren", "Validate"))
    st.success(tr("Review bereit für finalen Export-Check.", "Review ready for final export check."))
    st.subheader("Nav")
    st.caption(
        tr(
            "Navigation über die Wizard-Buttons unten (Zurück/Weiter).",
            "Use wizard navigation buttons below (Back/Next).",
        )
    )


def step_review(context: WizardContext) -> None:
    render_review_step(context)
