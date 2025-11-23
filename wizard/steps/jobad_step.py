from __future__ import annotations

from types import ModuleType
from typing import Mapping

import streamlit as st

from constants.keys import StateKeys, UIKeys
from utils.i18n import tr
from wizard.components.extraction_settings_panel import render_extraction_settings_panel
from wizard.layout import render_step_heading, render_step_warning_banner
from wizard_router import WizardContext


def _get_flow_module() -> ModuleType:
    """Return the lazily imported ``wizard.flow`` module."""

    from wizard import flow as wizard_flow

    return wizard_flow


def _render_jobad_step_v2(schema: Mapping[str, object]) -> None:
    """Render the onboarding and metadata step for the Job Ad flow."""

    flow = _get_flow_module()
    flow._render_onboarding_hero()
    _step_onboarding(dict(schema))


def _prime_extraction_settings_state() -> None:
    """Ensure extraction-related session keys exist before rendering widgets."""

    strict_value = st.session_state.get(StateKeys.EXTRACTION_STRICT_FORMAT, True)
    strict_enabled = bool(strict_value) if strict_value is not None else True
    st.session_state[StateKeys.EXTRACTION_STRICT_FORMAT] = strict_enabled
    st.session_state[UIKeys.EXTRACTION_STRICT_FORMAT] = bool(
        st.session_state.get(UIKeys.EXTRACTION_STRICT_FORMAT, strict_enabled)
    )

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

    onboarding_header = flow._format_dynamic_message(
        default=(
            "Intelligenzgestützter Recruiting-Kickstart",
            "Intelligence-powered recruiting kickoff",
        ),
        context=profile_context,
        variants=[
            (
                (
                    "Intelligenzgestützter Recruiting-Kickstart für {job_title} bei {company_name}",
                    "Intelligence-powered recruiting kickoff for {job_title} at {company_name}",
                ),
                ("job_title", "company_name"),
            ),
            (
                (
                    "Intelligenzgestützter Recruiting-Kickstart für {job_title}",
                    "Intelligence-powered recruiting kickoff for {job_title}",
                ),
                ("job_title",),
            ),
        ],
    )
    onboarding_caption = flow._format_dynamic_message(
        default=(
            "Teile den Einstieg über URL oder Datei und sichere jede relevante Insight gleich am Anfang.",
            "Share a URL or file to capture every crucial insight from the very first step.",
        ),
        context=profile_context,
        variants=[
            (
                (
                    "Übermittle den Startpunkt für {job_title} bei {company_name} über URL oder Datei und sichere jede Insight.",
                    "Provide the entry point for {job_title} at {company_name} via URL or upload to secure every insight.",
                ),
                ("job_title", "company_name"),
            ),
            (
                (
                    "Übermittle den Startpunkt für {job_title} über URL oder Datei und sichere jede Insight.",
                    "Provide the entry point for the {job_title} role via URL or upload to secure every insight.",
                ),
                ("job_title",),
            ),
        ],
    )
    render_step_heading(onboarding_header, onboarding_caption)
    render_step_warning_banner()

    flow._inject_onboarding_source_styles()

    intro_lines = [
        tr(
            "Unstrukturierte Bedarfsklärung verbrennt gleich im ersten Schritt kostbare Recruiting-Insights.",
            "Unstructured intake burns expensive recruiting intelligence in the very first step.",
        ),
        tr(
            "Unsere OpenAI-API-Agents erfassen jedes Detail und strukturieren Anforderungen in Echtzeit.",
            "Our OpenAI API agents capture every nuance and structure requirements in real time.",
        ),
        tr(
            "ESCO-Skillgraph und Marktprofile liefern Kontext für Skills, Seniorität und Branchensprache.",
            "ESCO skill graphs and market profiles add context for skills, seniority, and industry language.",
        ),
        tr(
            "Ein dynamischer Info-Gathering-Prozess baut einen vollständigen Datensatz für diese Vakanz auf.",
            "A dynamic info gathering process assembles a complete dataset for this specific vacancy.",
        ),
        tr(
            "So entstehen Inputs für interne Kommunikations-Automation & Folgeschritte – Ziel: glückliche Kandidat:innen nachhaltig platzieren.",
            "These inputs fuel internal communication automation and downstream steps – goal: place happy candidates sustainably.",
        ),
    ]

    intro_html = "<br/>".join(intro_lines)
    st.markdown(f"<div class='onboarding-intro'>{intro_html}</div>", unsafe_allow_html=True)

    st.divider()

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

    st.markdown(
        "<div class='onboarding-source-marker' style='display:none'></div>",
        unsafe_allow_html=True,
    )
    url_column, upload_column = st.columns(2, gap="large")
    with url_column:
        st.text_input(
            tr("Stellenanzeigen-URL einfügen", "Provide the job posting URL"),
            key=UIKeys.PROFILE_URL_INPUT,
            on_change=flow.on_url_changed,
            placeholder=tr("Bitte URL eingeben", "Enter the job posting URL"),
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
                "Upload job posting (PDF/DOCX/TXT)",
            ),
            type=["pdf", "docx", "txt"],
            key=UIKeys.PROFILE_FILE_UPLOADER,
            on_change=flow.on_file_uploaded,
            help=tr(
                "Direkt nach dem Upload beginnen wir mit der Analyse.",
                "We start analysing immediately after the upload finishes.",
            ),
            disabled=locked,
        )

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
