"""Rendering helpers for the interview guide generation panel."""

from __future__ import annotations

import logging
import re
from typing import Mapping

import streamlit as st

from constants.keys import StateKeys, UIKeys
from models.need_analysis import NeedAnalysisProfile
from utils.export import prepare_download_data
from utils.i18n import tr
from utils.llm_state import is_llm_available, llm_disabled_message
from wizard._agents import generate_interview_guide_content
from wizard._logic import _get_company_logo_bytes
from wizard.layout import render_section_heading

logger = logging.getLogger(__name__)

__all__ = ["render_interview_guide_section"]

_GENERATION_REQUEST_KEY = "interview_generation_request"
_GENERATION_STATUS_KEY = "interview_generation_status"


def _textarea_height(content: str) -> int:
    """Return a reasonable text area height based on the line count."""

    if not content:
        return 240
    line_count = content.count("\n") + 1
    return min(900, max(240, line_count * 28))


def _queue_interview_generation(audience: str, num_questions: int) -> None:
    """Flag an interview guide generation request with the chosen settings."""

    st.session_state[_GENERATION_REQUEST_KEY] = {
        "audience": audience,
        "num_questions": num_questions,
    }
    st.session_state[_GENERATION_STATUS_KEY] = "pending"
    st.session_state["interview_guide_warning"] = None
    st.session_state["interview_guide_error"] = None
    st.session_state["interview_guide_fallback_detail"] = None


def _run_pending_interview_generation(
    profile_payload: Mapping[str, object],
    lang: str,
) -> None:
    """Execute a queued interview guide generation request exactly once."""

    request = st.session_state.pop(_GENERATION_REQUEST_KEY, None)
    if not request:
        return

    num_questions = int(request.get("num_questions", 5))
    audience = str(request.get("audience") or "general")
    st.session_state[_GENERATION_STATUS_KEY] = "running"
    success = generate_interview_guide_content(
        profile_payload,
        lang,
        num_questions,
        audience=audience,
        warn_on_length=True,
        show_error=False,
    )
    status = st.session_state.get("interview_guide_status")
    st.session_state[_GENERATION_STATUS_KEY] = status or ("success" if success else "error")


def render_interview_guide_section(
    profile: NeedAnalysisProfile,
    profile_payload: Mapping[str, object],
    *,
    lang: str,
    style_label: str | None = None,
    style_description: str | None = None,
) -> None:
    """Render the interactive panel for generating interview guides."""

    render_section_heading(
        tr("2. Interview-Prep-Sheet", "2. Interview prep sheet"),
        icon="🗒️",
    )
    st.caption(
        tr(
            "Erstelle Leitfäden und passe sie an verschiedene Zielgruppen an.",
            "Generate guides and tailor them for different audiences.",
        )
    )

    _run_pending_interview_generation(profile_payload, lang)

    tone_col, question_col = st.columns((1, 1), gap="small")
    style_label_text = (style_label or "").strip()
    style_description_text = (style_description or "").strip()

    with tone_col:
        st.markdown(f"**{tr('Interviewleitfaden-Stil', 'Interview guide style')}**")
        if style_label_text:
            st.caption(style_label_text)
        if style_description_text:
            st.caption(style_description_text)
        st.caption(
            tr(
                "Passe den Stil jederzeit über die Einstellungen in der Sidebar an.",
                "Adjust the style at any time via the settings in the sidebar.",
            )
        )

    with question_col:
        if UIKeys.NUM_QUESTIONS not in st.session_state:
            st.session_state[UIKeys.NUM_QUESTIONS] = 5
        st.slider(
            tr("Anzahl Interviewfragen", "Number of interview questions"),
            min_value=3,
            max_value=10,
            key=UIKeys.NUM_QUESTIONS,
        )

    audience_labels = {
        "general": tr("Allgemeines Interviewteam", "General interview panel"),
        "technical": tr("Technisches Fachpublikum", "Technical panel"),
        "leadership": tr("Führungsteam", "Leadership panel"),
    }
    if UIKeys.AUDIENCE_SELECT not in st.session_state:
        st.session_state[UIKeys.AUDIENCE_SELECT] = st.session_state.get(
            StateKeys.INTERVIEW_AUDIENCE,
            "general",
        )
    audience = st.selectbox(
        tr("Interview-Zielgruppe", "Interview audience"),
        options=list(audience_labels.keys()),
        format_func=lambda key: audience_labels.get(key, key),
        key=UIKeys.AUDIENCE_SELECT,
        help=tr(
            "Steuert Fokus und Tonfall des generierten Leitfadens.",
            "Controls the focus and tone of the generated guide.",
        ),
        width="stretch",
    )
    st.session_state[StateKeys.INTERVIEW_AUDIENCE] = audience

    selected_num = st.session_state.get(UIKeys.NUM_QUESTIONS, 5)

    generate_label = tr("Interviewleitfaden generieren", "Generate Interview Guide")
    llm_available = is_llm_available()
    if not llm_available:
        st.caption(llm_disabled_message())
    if st.button(generate_label, type="primary", disabled=not llm_available):
        _queue_interview_generation(audience, selected_num)
        st.rerun()

    status = st.session_state.get(_GENERATION_STATUS_KEY)
    if status == "running":
        st.info(tr("Leitfaden wird generiert…", "Generating interview guide…"))

    warning_message = st.session_state.get("interview_guide_warning")
    if warning_message:
        st.warning(warning_message)

    error_message = st.session_state.get("interview_guide_error")
    if status == "error" and error_message:
        st.error(
            tr(
                "Interviewleitfaden-Generierung fehlgeschlagen: {error}. Bitte erneut versuchen.",
                "Interview guide generation failed: {error}. Please try again.",
            ).format(error=error_message)
        )

    fallback_detail = st.session_state.get("interview_guide_fallback_detail")
    if status == "success" and fallback_detail:
        st.info(
            tr(
                "Interviewleitfaden aus Vorlage, da die KI nicht erreichbar war. (Details: {details})",
                "Showing fallback interview guide because the AI service was unavailable. (Details: {details})",
            ).format(details=fallback_detail)
        )

    guide_text = st.session_state.get(StateKeys.INTERVIEW_GUIDE_MD, "")
    if guide_text:
        output_key = UIKeys.INTERVIEW_OUTPUT
        if output_key not in st.session_state or st.session_state.get(output_key) != guide_text:
            st.session_state[output_key] = guide_text
        st.text_area(
            tr("Generierter Leitfaden", "Generated guide"),
            height=_textarea_height(guide_text),
            key=output_key,
        )

        guide_format = st.session_state.get(UIKeys.JOB_AD_FORMAT, "docx")
        font_choice = st.session_state.get(StateKeys.JOB_AD_FONT_CHOICE)
        logo_bytes = _get_company_logo_bytes()
        guide_title = profile.position.job_title or "interview-guide"
        safe_stem = re.sub(r"[^A-Za-z0-9_-]+", "-", guide_title).strip("-") or "interview-guide"
        export_font = font_choice if guide_format in {"docx", "pdf"} else None
        export_logo = logo_bytes if guide_format in {"docx", "pdf"} else None
        payload, mime, ext = prepare_download_data(
            guide_text,
            guide_format,
            key="interview",
            title=guide_title,
            font=export_font,
            logo=export_logo,
            company_name=profile.company.name,
        )
        st.download_button(
            tr("⬇️ Leitfaden herunterladen", "⬇️ Download guide"),
            payload,
            file_name=f"{safe_stem}.{ext}",
            mime=mime,
            key="download_interview",
        )
