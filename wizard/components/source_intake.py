from __future__ import annotations

from types import ModuleType

import streamlit as st

from constants.keys import StateKeys, UIKeys
from utils.i18n import tr


def render_source_intake(*, flow: ModuleType, lang: str) -> None:
    """Render the shared source intake controls (URL, upload, free text)."""

    st.markdown("<div id='onboarding-source-inputs'></div>", unsafe_allow_html=True)
    st.markdown("<div class='onboarding-source-inputs'>", unsafe_allow_html=True)
    url_column, or_column, upload_column = st.columns([1, 0.18, 1], gap="large")
    with url_column:
        st.markdown("<div class='onboarding-source__panel'>", unsafe_allow_html=True)
        st.text_input(
            tr("Stellenanzeigen-URL hinzufügen", "Add the job posting URL", lang=lang),
            key=UIKeys.PROFILE_URL_INPUT,
            on_change=flow.on_url_changed,
            placeholder=tr("Stellenanzeigen-URL eingeben", "Enter the job posting URL", lang=lang),
            help=tr(
                "Die URL muss ohne Login erreichbar sein. Wir übernehmen den Inhalt automatisch.",
                "The URL needs to be accessible without authentication. We will fetch the content automatically.",
                lang=lang,
            ),
        )
        st.caption(
            tr(
                "Für öffentliche Karriereseiten oder Jobbörsen.",
                "Best for public career pages or job boards.",
                lang=lang,
            )
        )
        st.markdown("</div>", unsafe_allow_html=True)

    with or_column:
        st.markdown(
            f"<div class='onboarding-source__or'><span>{tr('oder', 'or', lang=lang)}</span></div>",
            unsafe_allow_html=True,
        )

    with upload_column:
        st.markdown("<div class='onboarding-source__panel'>", unsafe_allow_html=True)
        st.file_uploader(
            tr("Stellenanzeige hochladen (PDF/DOCX/TXT)", "Upload the job posting (PDF/DOCX/TXT)", lang=lang),
            type=["pdf", "docx", "txt"],
            key=UIKeys.PROFILE_FILE_UPLOADER,
            on_change=flow.on_file_uploaded,
            help=tr(
                "Nach dem Upload starten wir sofort die Analyse.",
                "We start the analysis right after the upload finishes.",
                lang=lang,
            ),
        )
        st.caption(
            tr(
                "Ideal für interne Dokumente oder passwortgeschützte Dateien.",
                "Ideal for internal documents or files behind a login.",
                lang=lang,
            )
        )
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def render_source_status(*, lang: str) -> None:
    """Render extraction status and source import errors for intake."""

    if st.session_state.get("source_error"):
        fallback_message = tr(
            "Es gab ein Problem beim Import. Versuche URL oder Upload erneut oder kontaktiere unser Support-Team.",
            "There was an issue while importing the content. Retry the URL/upload or contact our support team.",
            lang=lang,
        )
        error_text = st.session_state.get("source_error_message") or fallback_message
        st.error(error_text)

    extraction_summary = st.session_state.get(StateKeys.EXTRACTION_SUMMARY)
    if isinstance(extraction_summary, str) and extraction_summary.strip() and not st.session_state.get("source_error"):
        st.info(extraction_summary)
