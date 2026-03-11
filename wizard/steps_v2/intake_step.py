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

_SUMMARY_FIELDS = ("intake.source_language", "intake.target_locale")


def render_intake_step(context: WizardContext) -> None:
    profile = get_profile_data()
    st.header("Intake")
    st.markdown(tr("Prüfe die importierten Ausgangsdaten als Basis.", "Review imported intake data as baseline."))

    st.subheader(tr("Bekannt", "Known"))
    render_summary_chips(_SUMMARY_FIELDS, profile)

    st.subheader(tr("Fehlend", "Missing (Top Questions)"))
    required_paths = render_v2_step(context=context, step_key="intake")
    top, optional = collect_top_questions(
        profile=profile, required_paths=required_paths, followup_prefixes=("intake.",)
    )
    render_question_cards(top)
    if optional:
        with st.expander(tr("Weitere Fragen (optional)", "More questions (optional)")):
            render_question_cards(optional)

    with st.form("v2_intake_form"):
        raw_input = st.text_area(
            "intake.raw_input", value=str(get_value(profile, "intake.raw_input") or ""), height=160
        )
        source_language = st.text_input(
            "intake.source_language", value=str(get_value(profile, "intake.source_language") or "")
        )
        target_locale = st.text_input(
            "intake.target_locale", value=str(get_value(profile, "intake.target_locale") or "")
        )
        submitted = st.form_submit_button(tr("Änderungen speichern", "Save changes"), type="primary")

    if submitted:
        updates: dict[str, Any] = {
            "intake.raw_input": raw_input.strip(),
            "intake.source_language": source_language.strip(),
            "intake.target_locale": target_locale.strip(),
        }
        commit_profile(profile, updates, context_update=context.update_profile)
        st.success(tr("Intake gespeichert.", "Intake saved."))

    tools_questions = collect_followup_questions(profile=profile, followup_prefixes=("intake.",))
    if tools_questions:
        with st.expander(tr("Tools", "Tools")):
            render_question_cards(tools_questions)

    st.subheader(tr("Validieren", "Validate"))
    missing = [path for path in required_paths if value_missing(get_value(profile, path))]
    if missing:
        st.warning("\n".join(f"- `{path}`" for path in missing))
    else:
        st.success(tr("Pflichtfelder vollständig.", "Required fields complete."))

    st.subheader("Nav")
    st.caption(
        tr(
            "Navigation über die Wizard-Buttons unten (Zurück/Weiter).",
            "Use wizard navigation buttons below (Back/Next).",
        )
    )


def step_intake(context: WizardContext) -> None:
    render_intake_step(context)
