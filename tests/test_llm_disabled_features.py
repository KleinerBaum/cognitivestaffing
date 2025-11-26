from __future__ import annotations

import streamlit as st

from constants.keys import StateKeys, UIKeys
from wizard._agents import generate_interview_guide_content, generate_job_ad_content


def _reset_state() -> None:
    st.session_state.clear()
    st.session_state["openai_api_key_missing"] = True


def test_generate_job_ad_content_skips_when_llm_disabled(monkeypatch) -> None:
    _reset_state()

    def _fail(*_args, **_kwargs):  # pragma: no cover - guard ensures no call
        raise AssertionError("LLM helpers should not be invoked when disabled")

    monkeypatch.setattr("wizard._agents.generate_job_ad", _fail)
    monkeypatch.setattr("wizard._agents.stream_job_ad", _fail)

    st.session_state[UIKeys.TONE_SELECT] = "neutral"

    result = generate_job_ad_content(
        filtered_profile={"position": {"job_title": "Engineer"}},
        selected_fields={"position.job_title"},
        target_value="general",
        manual_entries=[],
        style_reference=None,
        lang="en",
        show_error=False,
    )

    assert result is False
    assert StateKeys.JOB_AD_MD not in st.session_state
    assert StateKeys.JOB_AD_PREVIEW not in st.session_state


def test_generate_interview_guide_content_skips_when_llm_disabled(monkeypatch) -> None:
    _reset_state()

    def _fail(*_args, **_kwargs):  # pragma: no cover - guard ensures no call
        raise AssertionError("Interview guide helper should not run when LLM is disabled")

    monkeypatch.setattr("wizard._agents.generate_interview_guide", _fail)

    result = generate_interview_guide_content(
        profile_payload={"position": {"job_title": "Engineer"}},
        lang="en",
        selected_num=5,
        audience="general",
        show_error=False,
    )

    assert result is False
    assert StateKeys.INTERVIEW_GUIDE_MD not in st.session_state
    assert StateKeys.INTERVIEW_GUIDE_PREVIEW not in st.session_state
