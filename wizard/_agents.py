"""Agent call helpers used by the wizard UI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Collection, Mapping, Sequence

import streamlit as st

from config import VECTOR_STORE_ID
from constants.keys import StateKeys, UIKeys
from utils.i18n import tr
from utils.llm_state import is_llm_available, llm_disabled_message
from nlp.bias import scan_bias_language
from llm.interview import generate_interview_guide
from wizard._openai_bridge import generate_job_ad, stream_job_ad


@dataclass
class InterviewGuideGenerationResult:
    """Structured response for interview guide generation."""

    success: bool
    guide_md: str = ""
    guide_data: Mapping[str, Any] | None = None
    warning: str | None = None
    error: str | None = None
    fallback_detail: str | None = None
    fallback_used: bool = False
    chat_fallback_used: bool = False


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
        """Fallback synchronous job ad generation when streaming is unavailable."""

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

    st.session_state[StateKeys.JOB_AD_PREVIEW] = job_ad_md
    findings = scan_bias_language(job_ad_md, lang)
    st.session_state[StateKeys.BIAS_FINDINGS] = findings
    return True


def prepare_interview_guide_generation(
    profile_payload: Mapping[str, Any],
    lang: str,
    selected_num: int,
    *,
    audience: str = "general",
    warn_on_length: bool = True,
) -> InterviewGuideGenerationResult:
    """Build an interview guide without rendering UI components."""

    if not is_llm_available():
        return InterviewGuideGenerationResult(success=False, error=llm_disabled_message())

    requirements_data = dict(profile_payload.get("requirements", {}) or {})
    extras = (
        len(requirements_data.get("hard_skills_required", []))
        + len(requirements_data.get("hard_skills_optional", []))
        + len(requirements_data.get("soft_skills_required", []))
        + len(requirements_data.get("soft_skills_optional", []))
        + (1 if (profile_payload.get("company", {}) or {}).get("culture") else 0)
    )

    length_warning: str | None = None
    if warn_on_length and selected_num + extras > 15:
        length_warning = tr(
            "Viele Fragen erzeugen einen sehr umfangreichen Leitfaden.",
            "A high question count creates a very long guide.",
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
        return InterviewGuideGenerationResult(success=False, error=str(exc))

    guide = result.guide
    guide_md = guide.final_markdown()
    return InterviewGuideGenerationResult(
        success=True,
        guide_md=guide_md,
        guide_data=guide.model_dump(),
        warning=length_warning,
        error=None,
        fallback_used=result.used_fallback,
        chat_fallback_used=result.used_chat_fallback,
        fallback_detail=(result.error_detail or "").strip() or None,
    )


def _store_interview_result(result: InterviewGuideGenerationResult, audience: str) -> None:
    """Persist interview guide results and any warnings/errors into session state."""

    st.session_state[StateKeys.INTERVIEW_AUDIENCE] = audience
    st.session_state.setdefault(UIKeys.AUDIENCE_SELECT, audience)
    if result.success:
        st.session_state[StateKeys.INTERVIEW_GUIDE_PREVIEW] = result.guide_md
        st.session_state.pop(StateKeys.INTERVIEW_GUIDE_MD, None)
        st.session_state[StateKeys.INTERVIEW_GUIDE_DATA] = result.guide_data or {}
    else:
        st.session_state.pop(StateKeys.INTERVIEW_GUIDE_MD, None)
        st.session_state.pop(StateKeys.INTERVIEW_GUIDE_PREVIEW, None)
        st.session_state.pop(StateKeys.INTERVIEW_GUIDE_DATA, None)
    st.session_state["interview_guide_warning"] = result.warning
    st.session_state["interview_guide_error"] = result.error
    st.session_state["interview_guide_fallback_detail"] = result.fallback_detail if result.fallback_used else None
    st.session_state["interview_guide_used_chat_fallback"] = bool(result.chat_fallback_used)
    st.session_state["interview_guide_status"] = "success" if result.success else "error" if result.error else "empty"


def generate_interview_guide_content(
    profile_payload: Mapping[str, Any],
    lang: str,
    selected_num: int,
    *,
    audience: str = "general",
    warn_on_length: bool = True,
    show_error: bool = True,
) -> bool:
    """Generate the interview guide and update session state without inline UI rendering."""

    st.session_state["interview_guide_show_feedback"] = bool(show_error)
    result = prepare_interview_guide_generation(
        profile_payload,
        lang,
        selected_num,
        audience=audience,
        warn_on_length=warn_on_length,
    )
    _store_interview_result(result, audience)
    return result.success


__all__ = [
    "InterviewGuideGenerationResult",
    "prepare_interview_guide_generation",
    "generate_interview_guide_content",
    "generate_job_ad_content",
]
