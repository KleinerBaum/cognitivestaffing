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

logger = logging.getLogger(__name__)

__all__ = ["render_interview_guide_section"]


def _textarea_height(content: str) -> int:
    if not content:
        return 240
    line_count = content.count("\n") + 1
    return min(900, max(240, line_count * 28))


def render_interview_guide_section(
    profile: NeedAnalysisProfile,
    profile_payload: Mapping[str, object],
    *,
    lang: str,
    style_label: str | None = None,
    style_description: str | None = None,
) -> None:
    """Render the interactive panel for generating interview guides."""

    st.markdown(tr("### 2. Interview-Prep-Sheet", "### 2. Interview prep sheet"))
    st.caption(
        tr(
            "Erstelle Leitfäden und passe sie an verschiedene Zielgruppen an.",
            "Generate guides and tailor them for different audiences.",
        )
    )

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
    )
    st.session_state[StateKeys.INTERVIEW_AUDIENCE] = audience

    selected_num = st.session_state.get(UIKeys.NUM_QUESTIONS, 5)

    generate_label = tr("Interviewleitfaden generieren", "Generate Interview Guide")
    llm_available = is_llm_available()
    if not llm_available:
        st.caption(llm_disabled_message())
    if st.button(generate_label, type="primary", disabled=not llm_available):
        if not llm_available:
            return
        with st.spinner(tr("Leitfaden wird generiert…", "Generating interview guide…")):
            try:
                success = generate_interview_guide_content(
                    profile_payload,
                    lang,
                    selected_num,
                    audience=audience,
                )
            except Exception as exc:  # pragma: no cover - defensive UI guard
                logger.exception("Interview guide generation failed")
                st.error(
                    tr(
                        "Interviewleitfaden-Generierung fehlgeschlagen: {error}. Bitte erneut versuchen.",
                        "Interview guide generation failed: {error}. Please try again.",
                    ).format(error=exc)
                )
            else:
                if not success:
                    st.warning(
                        tr(
                            "Konnte keinen Interviewleitfaden erzeugen. Bitte erneut versuchen.",
                            "Unable to generate an interview guide. Please try again.",
                        )
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
