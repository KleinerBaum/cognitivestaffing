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
    parse_multiline,
    render_question_cards,
    render_summary_chips,
    value_missing,
)

_SUMMARY_FIELDS = ("selection.process_steps", "selection.stakeholders")
_REQUIRED = ("selection.process_steps",)


def render_selection_step(context: WizardContext) -> None:
    profile = get_profile_data()
    st.header("Selection")
    st.subheader(tr("Bekannt", "Known"))
    render_summary_chips(_SUMMARY_FIELDS, profile)

    st.subheader(tr("Fehlend", "Missing (Top Questions)"))
    top, optional = collect_top_questions(profile=profile, required_paths=_REQUIRED, followup_prefixes=("selection.",))
    render_question_cards(top)
    if optional:
        with st.expander(tr("Weitere Fragen (optional)", "More questions (optional)")):
            render_question_cards(optional)

    process_raw = get_value(profile, "selection.process_steps")
    stakeholders_raw = get_value(profile, "selection.stakeholders")
    with st.form("v2_selection_form"):
        process_steps = st.text_area(
            "selection.process_steps",
            value="\n".join(process_raw) if isinstance(process_raw, list) else str(process_raw or ""),
            height=120,
        )
        stakeholders = st.text_area(
            "selection.stakeholders",
            value="\n".join(stakeholders_raw) if isinstance(stakeholders_raw, list) else str(stakeholders_raw or ""),
            height=120,
        )
        submitted = st.form_submit_button(tr("Änderungen speichern", "Save changes"), type="primary")
    if submitted:
        updates: dict[str, Any] = {
            "selection.process_steps": parse_multiline(process_steps),
            "selection.stakeholders": parse_multiline(stakeholders),
        }
        commit_profile(profile, updates, context_update=context.update_profile)
        st.success(tr("Selection gespeichert.", "Selection saved."))

    tools_questions = collect_followup_questions(profile=profile, followup_prefixes=("selection.",))
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


def step_selection(context: WizardContext) -> None:
    render_selection_step(context)
