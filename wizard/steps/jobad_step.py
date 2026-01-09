from __future__ import annotations

from types import ModuleType
from typing import Mapping

import streamlit as st

from constants.keys import StateKeys, UIKeys
from utils.i18n import tr
from wizard.components.extraction_settings_panel import render_extraction_settings_panel
from wizard.layout import build_onboarding_hero_copy, render_section_heading, render_step_warning_banner
from wizard_router import WizardContext


def _get_flow_module() -> ModuleType:
    """Return the lazily imported ``wizard.flow`` module."""

    from wizard import flow as wizard_flow

    return wizard_flow


def _render_jobad_step_v2(schema: Mapping[str, object]) -> None:
    """Render the onboarding and metadata step for the Job Ad flow."""

    _step_onboarding(dict(schema))


def _prime_extraction_settings_state() -> None:
    """Ensure extraction-related session keys exist before rendering widgets."""

    st.session_state[StateKeys.EXTRACTION_STRICT_FORMAT] = True
    st.session_state[UIKeys.EXTRACTION_STRICT_FORMAT] = True

    reasoning_mode = str(st.session_state.get(StateKeys.REASONING_MODE, "precise") or "precise").strip().lower()
    st.session_state[UIKeys.EXTRACTION_REASONING_MODE] = reasoning_mode


def _step_onboarding(schema: dict) -> None:
    """Render onboarding with language toggle, intro, and ingestion options."""

    flow = _get_flow_module()
    flow._maybe_run_extraction(schema)

    if UIKeys.LANG_SELECT not in st.session_state:
        st.session_state[UIKeys.LANG_SELECT] = st.session_state.get("lang", "de")

    st.session_state["lang"] = st.session_state[UIKeys.LANG_SELECT]

    profile = flow._get_profile_state()
    profile_context = flow._build_profile_context(profile)

    hero_copy = build_onboarding_hero_copy(
        format_message=flow._format_dynamic_message,
        profile_context=profile_context,
    )
    flow._render_onboarding_hero(hero_copy)
    render_step_warning_banner()

    with st.container():
        st.markdown("<div id='onboarding-source'></div>", unsafe_allow_html=True)
        render_section_heading(
            tr("Stellenanzeige bereitstellen", "Provide the job posting"),
            icon="📌",
        )

        if st.session_state.get("source_error"):
            fallback_message = tr(
                "Es gab ein Problem beim Import. Versuche URL oder Upload erneut oder kontaktiere unser Support-Team.",
                "There was an issue while importing the content. Retry the URL/upload or contact our support team.",
            )
            error_text = st.session_state.get("source_error_message") or fallback_message
            st.error(error_text)

        prefill = st.session_state.pop("__prefill_profile_text__", None)
        if prefill is not None:
            st.session_state[UIKeys.PROFILE_TEXT_INPUT] = prefill
            st.session_state[StateKeys.RAW_TEXT] = prefill
            doc_prefill = st.session_state.get("__prefill_profile_doc__")
            if doc_prefill:
                st.session_state[StateKeys.RAW_BLOCKS] = doc_prefill.blocks

        locked = flow._is_onboarding_locked()

        st.markdown("<div class='onboarding-source-inputs'>", unsafe_allow_html=True)
        url_column, upload_column = st.columns(2, gap="large")
        with url_column:
            st.text_input(
                tr("Stellenanzeigen-URL hinzufügen", "Add the job posting URL"),
                key=UIKeys.PROFILE_URL_INPUT,
                on_change=flow.on_url_changed,
                placeholder=tr("Stellenanzeigen-URL eingeben", "Enter the job posting URL"),
                help=tr(
                    "Die URL muss ohne Login erreichbar sein. Wir übernehmen den Inhalt automatisch.",
                    "The URL needs to be accessible without authentication. We will fetch the content automatically.",
                ),
                disabled=locked,
            )

        with upload_column:
            st.file_uploader(
                tr(
                    "Stellenanzeige hochladen (PDF/DOCX/TXT)",
                    "Upload the job posting (PDF/DOCX/TXT)",
                ),
                type=["pdf", "docx", "txt"],
                key=UIKeys.PROFILE_FILE_UPLOADER,
                on_change=flow.on_file_uploaded,
                help=tr(
                    "Nach dem Upload starten wir sofort die Analyse.",
                    "We start the analysis right after the upload finishes.",
                ),
                disabled=locked,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    with st.expander(tr("Was passiert?", "What happens?"), expanded=False):
        intro_lines = [
            tr(
                "Eine klare Stellenanzeige hilft, Anforderungen direkt von Anfang an zu erfassen.",
                "A clear job posting helps capture requirements right from the start.",
            ),
            tr(
                "Unsere OpenAI-API-Agents extrahieren Inhalte und strukturieren sie in Echtzeit.",
                "Our OpenAI API agents extract the content and structure it in real time.",
            ),
            tr(
                "ESCO-Skillgraph und Marktprofile liefern Kontext für Skills, Seniorität und Branchensprache.",
                "ESCO skill graphs and market profiles add context for skills, seniority, and industry language.",
            ),
            tr(
                "Der dynamische Fragenprozess ergänzt fehlende Details Schritt für Schritt.",
                "The dynamic question flow fills in missing details step by step.",
            ),
            tr(
                "So entsteht ein vollständiger Datensatz für die Vakanz und die folgenden Exporte.",
                "This builds a complete dataset for the role and the exports that follow.",
            ),
        ]

        intro_html = "<br/>".join(intro_lines)
        st.markdown(f"<div class='onboarding-intro'>{intro_html}</div>", unsafe_allow_html=True)

        _prime_extraction_settings_state()
        render_extraction_settings_panel(
            apply_parsing_mode=flow._apply_parsing_mode,
            queue_extraction_rerun=flow._queue_extraction_rerun,
            st_module=st,
        )

    review_rendered = flow._render_extraction_review()

    if not review_rendered:
        flow._render_followups_for_step("jobad", profile)

    if st.button(
        tr("Weiter ▶", "Next ▶"),
        type="primary",
        key="onboarding_next_compact",
        disabled=locked,
    ):
        flow._advance_from_onboarding()


def step_jobad(context: WizardContext) -> None:
    """Render the job ad intake step using ``context``."""

    _render_jobad_step_v2(context.schema)
