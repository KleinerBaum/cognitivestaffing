import json
from typing import Any

import pytest
import streamlit as st

from wizard import _skip_source, _extract_and_summarize, COMPANY_STEP_INDEX
from constants.keys import StateKeys
from models.need_analysis import NeedAnalysisProfile


def test_skip_source_resets_session(monkeypatch: pytest.MonkeyPatch) -> None:
    """_skip_source should clear profile-related state and advance the step."""

    st.session_state.clear()
    st.session_state[StateKeys.RAW_TEXT] = "old"
    st.session_state[StateKeys.PROFILE] = {"position": {"job_title": "X"}}
    st.session_state[StateKeys.EXTRACTION_SUMMARY] = {"foo": "bar"}
    st.session_state[StateKeys.EXTRACTION_MISSING] = ["company.name"]
    st.session_state[StateKeys.EXTRACTION_RAW_PROFILE] = {
        "requirements": {"hard_skills_required": ["Python"]}
    }
    st.session_state[StateKeys.ESCO_SKILLS] = ["Data Analysis"]
    st.session_state[StateKeys.SKILL_BUCKETS] = {
        "must": ["Python"],
        "nice": ["Excel"],
    }
    st.session_state[StateKeys.STEP] = 1
    st.session_state["_analyze_attempted"] = True
    monkeypatch.setattr(st, "rerun", lambda: None)

    _skip_source()

    assert st.session_state[StateKeys.STEP] == COMPANY_STEP_INDEX
    assert st.session_state[StateKeys.RAW_TEXT] == ""
    assert st.session_state[StateKeys.EXTRACTION_SUMMARY] == {}
    assert st.session_state[StateKeys.EXTRACTION_MISSING] == []
    assert st.session_state[StateKeys.EXTRACTION_RAW_PROFILE] == {}
    assert st.session_state[StateKeys.ESCO_SKILLS] == []
    assert st.session_state[StateKeys.SKILL_BUCKETS] == {"must": [], "nice": []}
    assert st.session_state[StateKeys.PROFILE] == NeedAnalysisProfile().model_dump()
    assert "_analyze_attempted" not in st.session_state


def test_extract_and_summarize_auto_reask(monkeypatch: pytest.MonkeyPatch) -> None:
    """_extract_and_summarize should populate follow-ups when auto_reask is on."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state.model = "gpt"
    st.session_state.auto_reask = True
    st.session_state.vector_store_id = ""

    def fake_extract(
        text: str, title: str | None = None, url: str | None = None, **_: Any
    ) -> str:
        return json.dumps({"meta": {"followups_answered": []}})

    def fake_coerce(data: dict) -> NeedAnalysisProfile:
        return NeedAnalysisProfile.model_validate(data)

    def fake_followups(
        payload: dict, model: str | None = None, vector_store_id: str | None = None
    ) -> dict:
        return {
            "questions": [
                {"field": "company.name", "question": "?", "priority": "critical"}
            ]
        }

    class _DummySpinner:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr("wizard.extract_json", fake_extract)
    monkeypatch.setattr("wizard.coerce_and_fill", fake_coerce)
    monkeypatch.setattr("wizard.apply_basic_fallbacks", lambda p, t: p)
    monkeypatch.setattr("wizard.ask_followups", fake_followups)
    monkeypatch.setattr(st, "spinner", lambda *a, **k: _DummySpinner())

    _extract_and_summarize("text", {})

    assert st.session_state[StateKeys.FOLLOWUPS] == [
        {"field": "company.name", "question": "?", "priority": "critical"}
    ]
    assert StateKeys.EXTRACTION_RAW_PROFILE in st.session_state
    assert StateKeys.SKILL_BUCKETS in st.session_state
