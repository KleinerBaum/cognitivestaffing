from __future__ import annotations

from types import ModuleType
from typing import Mapping

import streamlit as st

from constants.flow_mode import FlowMode
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
    """Render onboarding review and extraction settings."""

    flow = _get_flow_module()
    flow._maybe_run_extraction(schema)

    if UIKeys.LANG_SELECT not in st.session_state:
        st.session_state[UIKeys.LANG_SELECT] = st.session_state.get("lang", "de")

    st.session_state["lang"] = st.session_state[UIKeys.LANG_SELECT]

    profile = flow._get_profile_state()
    profile_context = flow._build_profile_context(profile)

    show_intro_banner = bool(st.session_state.get(UIKeys.INTRO_BANNER, True))
    with st.container():
        button_column, _ = st.columns([0.25, 0.75])
        with button_column:
            if show_intro_banner:
                if st.button("Intro ausblenden / Hide intro", key="onboarding.intro.hide"):
                    st.session_state[UIKeys.INTRO_BANNER] = False
            else:
                if st.button("Intro einblenden / Show intro", key="onboarding.intro.show"):
                    st.session_state[UIKeys.INTRO_BANNER] = True

    show_intro_banner = bool(st.session_state.get(UIKeys.INTRO_BANNER, True))
    hero_copy = build_onboarding_hero_copy(
        format_message=flow._format_dynamic_message,
        profile_context=profile_context,
    )
    if show_intro_banner:
        flow._render_onboarding_hero(hero_copy)
    render_step_warning_banner()

    with st.container():
        st.markdown("<div id='onboarding-source'></div>", unsafe_allow_html=True)
        render_section_heading(
            tr("Analyse prüfen & verfeinern", "Review and refine analysis"),
            icon="🔎",
        )
        st.caption(
            tr(
                "Import über URL/Upload/Freitext erfolgt im Willkommen-Schritt. Hier prüfen Sie das Ergebnis und verfeinern es bei Bedarf.",
                "URL/upload/free-text intake happens in the Welcome step. Review the extracted result here and refine it as needed.",
            )
        )

    with st.expander(
        tr("Details & Einstellungen / Details & settings", "Details & Einstellungen / Details & settings"),
        expanded=False,
    ):
        intro_lines = [
            tr(
                "Wir analysieren die Stellenanzeige Schritt für Schritt und extrahieren nur relevante Informationen.",
                "We analyze the job posting step by step and extract only relevant information.",
            ),
            tr(
                "Ihre Eingaben bleiben vertraulich; URLs und Uploads werden ausschließlich für dieses Profil verarbeitet.",
                "Your inputs stay confidential; URLs and uploads are processed only for this profile.",
            ),
            tr(
                "Die Extraktion läuft automatisiert, bleibt transparent und lässt sich jederzeit anpassen.",
                "Extraction runs automatically, stays transparent, and can be adjusted at any time.",
            ),
            tr(
                "Bitte prüfen Sie die Ergebnisse sorgfältig, damit Suche, Matching und Exporte präzise bleiben.",
                "Please review the results carefully so search, matching, and exports stay accurate.",
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

    review_rendered = False
    if flow.get_flow_mode() != FlowMode.SINGLE_PAGE:
        review_rendered = flow._render_extraction_review()

    if not review_rendered:
        flow._render_followups_for_step("jobad", profile)


def step_jobad(context: WizardContext) -> None:
    """Render the job ad intake step using ``context``."""

    _render_jobad_step_v2(context.schema)
