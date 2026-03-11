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

_SUMMARY_FIELDS = ("work.responsibilities", "work.location", "work.work_policy")
_REQUIRED = ("work.responsibilities",)


def render_real_work_step(context: WizardContext) -> None:
    profile = get_profile_data()
    st.header("Real Work")
    st.subheader(tr("Bekannt", "Known"))
    render_summary_chips(_SUMMARY_FIELDS, profile)

    st.subheader(tr("Fehlend", "Missing (Top Questions)"))
    top, optional = collect_top_questions(profile=profile, required_paths=_REQUIRED, followup_prefixes=("work.",))
    render_question_cards(top)
    if optional:
        with st.expander(tr("Weitere Fragen (optional)", "More questions (optional)")):
            render_question_cards(optional)

    current_responsibilities = get_value(profile, "work.responsibilities")
    initial = (
        "\n".join(current_responsibilities)
        if isinstance(current_responsibilities, list)
        else str(current_responsibilities or "")
    )
    with st.form("v2_real_work_form"):
        responsibilities = st.text_area("work.responsibilities", value=initial, height=160)
        location = st.text_input("work.location", value=str(get_value(profile, "work.location") or ""))
        work_policy = st.selectbox(
            "work.work_policy",
            options=["", "onsite", "hybrid", "remote"],
            index=["", "onsite", "hybrid", "remote"].index(str(get_value(profile, "work.work_policy") or ""))
            if str(get_value(profile, "work.work_policy") or "") in ["", "onsite", "hybrid", "remote"]
            else 0,
        )
        submitted = st.form_submit_button(tr("Änderungen speichern", "Save changes"), type="primary")
    if submitted:
        updates: dict[str, Any] = {
            "work.responsibilities": parse_multiline(responsibilities),
            "work.location": location.strip(),
            "work.work_policy": work_policy,
        }
        commit_profile(profile, updates, context_update=context.update_profile)
        st.success(tr("Real Work gespeichert.", "Real work saved."))

    tools_questions = collect_followup_questions(profile=profile, followup_prefixes=("work.",))
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


def step_real_work(context: WizardContext) -> None:
    render_real_work_step(context)
