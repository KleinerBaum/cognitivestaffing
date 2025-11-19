"""Agent call helpers used by the wizard UI."""

from __future__ import annotations

from typing import Any, Collection, Mapping, Sequence

import streamlit as st

from config import VECTOR_STORE_ID
from constants.keys import StateKeys, UIKeys
from utils.i18n import tr
from utils.llm_state import is_llm_available, llm_disabled_message
from nlp.bias import scan_bias_language
from llm.interview import generate_interview_guide
from wizard._openai_bridge import generate_job_ad, stream_job_ad


def generate_job_ad_content(
    filtered_profile: Mapping[str, Any],
    selected_fields: Collection[str],
    target_value: str | None,
    manual_entries: Sequence[dict[str, str]],
    style_reference: str | None,
    lang: str,
    *,
    show_error: bool = True,
) -> bool:
    """Generate the job ad and update session state."""

    if not selected_fields or not target_value:
        return False

    if not is_llm_available():
        if show_error:
            st.info(llm_disabled_message())
        return False

    raw_vector_store = st.session_state.get("vector_store_id") or VECTOR_STORE_ID
    vector_store_id = str(raw_vector_store).strip() if raw_vector_store else ""

    def _generate_sync() -> str:
        return generate_job_ad(
            filtered_profile,
            list(selected_fields),
            target_audience=target_value,
            manual_sections=list(manual_entries),
            style_reference=style_reference,
            tone=st.session_state.get(UIKeys.TONE_SELECT),
            lang=lang,
            selected_values=st.session_state.get(StateKeys.JOB_AD_SELECTED_VALUES, {}),
            vector_store_id=vector_store_id or None,
        )

    job_ad_md = ""
    placeholder = st.empty()
    spinner_label = tr("Anzeige wird generiert…", "Generating job ad…")

    if vector_store_id:
        try:
            job_ad_md = _generate_sync()
            placeholder.markdown(job_ad_md)
        except Exception as exc:  # pragma: no cover - error path
            if show_error:
                st.error(
                    tr(
                        "Job Ad Generierung fehlgeschlagen",
                        "Job ad generation failed",
                    )
                    + f": {exc}"
                )
            return False
    else:
        try:
            stream, fallback_doc = stream_job_ad(
                filtered_profile,
                list(selected_fields),
                target_audience=target_value,
                manual_sections=list(manual_entries),
                style_reference=style_reference,
                tone=st.session_state.get(UIKeys.TONE_SELECT),
                lang=lang,
                selected_values=st.session_state.get(StateKeys.JOB_AD_SELECTED_VALUES, {}),
            )
        except Exception:
            try:
                job_ad_md = _generate_sync()
                placeholder.markdown(job_ad_md)
            except Exception as exc:  # pragma: no cover - error path
                if show_error:
                    st.error(
                        tr(
                            "Job Ad Generierung fehlgeschlagen",
                            "Job ad generation failed",
                        )
                        + f": {exc}"
                    )
                return False
        else:
            chunks: list[str] = []
            try:
                with st.spinner(spinner_label):
                    for chunk in stream:
                        if not chunk:
                            continue
                        chunks.append(chunk)
                        placeholder.markdown("".join(chunks))
            except Exception as exc:  # pragma: no cover - network/SDK issues
                if show_error:
                    st.error(
                        tr(
                            "Job Ad Streaming fehlgeschlagen",
                            "Job ad streaming failed",
                        )
                        + f": {exc}"
                    )
                try:
                    job_ad_md = _generate_sync()
                    placeholder.markdown(job_ad_md)
                except Exception as sync_exc:  # pragma: no cover - error path
                    if show_error:
                        st.error(
                            tr(
                                "Job Ad Generierung fehlgeschlagen",
                                "Job ad generation failed",
                            )
                            + f": {sync_exc}"
                        )
                    return False
            else:
                try:
                    result = stream.result
                    job_ad_md = (result.content or stream.text or "").strip()
                except RuntimeError:
                    job_ad_md = (stream.text or "").strip()
                if not job_ad_md:
                    job_ad_md = fallback_doc
                placeholder.markdown(job_ad_md)

    st.session_state[StateKeys.JOB_AD_MD] = job_ad_md
    findings = scan_bias_language(job_ad_md, lang)
    st.session_state[StateKeys.BIAS_FINDINGS] = findings
    return True


def generate_interview_guide_content(
    profile_payload: Mapping[str, Any],
    lang: str,
    selected_num: int,
    *,
    audience: str = "general",
    warn_on_length: bool = True,
    show_error: bool = True,
) -> bool:
    """Generate the interview guide and update session state."""

    if not is_llm_available():
        if show_error:
            st.info(llm_disabled_message())
        return False

    st.session_state[StateKeys.INTERVIEW_AUDIENCE] = audience
    st.session_state.setdefault(UIKeys.AUDIENCE_SELECT, audience)

    requirements_data = dict(profile_payload.get("requirements", {}) or {})
    extras = (
        len(requirements_data.get("hard_skills_required", []))
        + len(requirements_data.get("hard_skills_optional", []))
        + len(requirements_data.get("soft_skills_required", []))
        + len(requirements_data.get("soft_skills_optional", []))
        + (1 if (profile_payload.get("company", {}) or {}).get("culture") else 0)
    )

    if warn_on_length and selected_num + extras > 15:
        st.warning(
            tr(
                "Viele Fragen erzeugen einen sehr umfangreichen Leitfaden.",
                "A high question count creates a very long guide.",
            )
        )

    responsibilities_text = "\n".join(profile_payload.get("responsibilities", {}).get("items", []))

    try:
        result = generate_interview_guide(
            job_title=profile_payload.get("position", {}).get("job_title", ""),
            responsibilities=responsibilities_text,
            hard_skills=(
                requirements_data.get("hard_skills_required", []) + requirements_data.get("hard_skills_optional", [])
            ),
            soft_skills=(
                requirements_data.get("soft_skills_required", []) + requirements_data.get("soft_skills_optional", [])
            ),
            company_culture=profile_payload.get("company", {}).get("culture", ""),
            audience=audience,
            lang=lang,
            tone=st.session_state.get("tone"),
            num_questions=selected_num,
        )
    except Exception as exc:  # pragma: no cover - error path
        if show_error:
            st.error(
                tr(
                    "Interviewleitfaden-Generierung fehlgeschlagen: {error}. Bitte erneut versuchen.",
                    "Interview guide generation failed: {error}. Please try again.",
                ).format(error=exc)
            )
        return False

    guide = result.guide
    st.session_state[StateKeys.INTERVIEW_GUIDE_DATA] = guide.model_dump()
    st.session_state[StateKeys.INTERVIEW_GUIDE_MD] = guide.final_markdown()

    if result.used_fallback and show_error:
        detail = (result.error_detail or "").strip()
        if detail:
            st.warning(
                tr(
                    "Die KI-Antwort konnte nicht verarbeitet werden. Wir zeigen vorübergehend den Standardleitfaden. (Details: {details})",
                    "The AI response could not be processed. Showing the standard guide for now. (Details: {details})",
                ).format(details=detail)
            )
        else:
            st.info(
                tr(
                    "Interviewleitfaden aus Vorlage, da die KI nicht erreichbar war.",
                    "Showing fallback interview guide because the AI service was unavailable.",
                )
            )

    return True


__all__ = [
    "generate_interview_guide_content",
    "generate_job_ad_content",
]
