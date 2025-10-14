import json
from typing import Any

import pytest
import streamlit as st

from wizard import (
    _skip_source,
    _extract_and_summarize,
    _advance_from_onboarding,
    COMPANY_STEP_INDEX,
    CRITICAL_SECTION_ORDER,
    next_step,
)
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
        text: str,
        title: str | None = None,
        company: str | None = None,
        url: str | None = None,
        locked_fields: dict[str, str] | None = None,
        **_: Any,
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
    monkeypatch.setattr("wizard.apply_basic_fallbacks", lambda p, t, **_: p)
    monkeypatch.setattr("wizard.ask_followups", fake_followups)
    monkeypatch.setattr(st, "spinner", lambda *a, **k: _DummySpinner())

    _extract_and_summarize("text", {})

    assert st.session_state[StateKeys.FOLLOWUPS] == [
        {"field": "company.name", "question": "?", "priority": "critical"}
    ]
    assert StateKeys.EXTRACTION_RAW_PROFILE in st.session_state
    assert StateKeys.SKILL_BUCKETS in st.session_state
    assert st.session_state[StateKeys.FIRST_INCOMPLETE_SECTION] == COMPANY_STEP_INDEX
    assert st.session_state[StateKeys.COMPLETED_SECTIONS] == []
    assert st.session_state[StateKeys.PENDING_INCOMPLETE_JUMP]


def test_extract_and_summarize_auto_reask_with_no_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ask_followups should be skipped when no fields are missing."""

    st.session_state.clear()
    st.session_state.lang = "en"
    st.session_state.model = "gpt"
    st.session_state.auto_reask = True
    st.session_state.vector_store_id = ""
    st.session_state["auto_reask_round"] = 3
    st.session_state["auto_reask_total"] = 3
    st.session_state[StateKeys.FOLLOWUPS] = [
        {"field": "company.name", "question": "?", "priority": "critical"}
    ]

    def fake_extract(
        text: str,
        title: str | None = None,
        company: str | None = None,
        url: str | None = None,
        locked_fields: dict[str, str] | None = None,
        **_: Any,
    ) -> str:
        return json.dumps({"meta": {"followups_answered": []}})

    def fake_coerce(data: dict) -> NeedAnalysisProfile:
        return NeedAnalysisProfile.model_validate(data)

    monkeypatch.setattr("wizard.extract_json", fake_extract)
    monkeypatch.setattr("wizard.coerce_and_fill", fake_coerce)
    monkeypatch.setattr("wizard.apply_basic_fallbacks", lambda p, t, **_: p)
    monkeypatch.setattr("wizard.CRITICAL_FIELDS", [])
    monkeypatch.setattr(
        "wizard.ask_followups", lambda *_, **__: pytest.fail("ask_followups called")
    )

    class _DummySpinner:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    monkeypatch.setattr(st, "spinner", lambda *a, **k: _DummySpinner())

    _extract_and_summarize("text", {})

    assert "auto_reask_round" in st.session_state
    assert st.session_state["auto_reask_round"] == 0
    assert "auto_reask_total" in st.session_state
    assert st.session_state["auto_reask_total"] == 0
    assert StateKeys.FOLLOWUPS not in st.session_state
    assert st.session_state[StateKeys.FIRST_INCOMPLETE_SECTION] is None
    assert st.session_state[StateKeys.COMPLETED_SECTIONS] == list(
        CRITICAL_SECTION_ORDER
    )
    assert not st.session_state[StateKeys.PENDING_INCOMPLETE_JUMP]


def test_next_step_advances_one_section() -> None:
    """next_step should move to the immediate next section."""

    st.session_state.clear()
    st.session_state[StateKeys.STEP] = 1
    st.session_state[StateKeys.WIZARD_STEP_COUNT] = 7
    st.session_state[StateKeys.COMPLETED_SECTIONS] = [1, 2, 3]
    st.session_state[StateKeys.PROFILE] = NeedAnalysisProfile().model_dump()

    next_step()

    assert st.session_state[StateKeys.STEP] == 2


def test_next_step_clears_pending_incomplete_jump_flag() -> None:
    """Manual navigation should clear pending incomplete jump flag."""

    st.session_state.clear()
    st.session_state[StateKeys.STEP] = 2
    st.session_state[StateKeys.WIZARD_STEP_COUNT] = 5
    st.session_state[StateKeys.PENDING_INCOMPLETE_JUMP] = True
    st.session_state[StateKeys.PROFILE] = NeedAnalysisProfile().model_dump()

    next_step()

    assert st.session_state[StateKeys.STEP] == 3
    assert not st.session_state.get(StateKeys.PENDING_INCOMPLETE_JUMP, False)


def test_onboarding_next_uses_first_incomplete_section(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Onboarding next button should jump to recorded incomplete section."""

    st.session_state.clear()
    st.session_state[StateKeys.STEP] = 0
    st.session_state[StateKeys.PENDING_INCOMPLETE_JUMP] = True
    st.session_state[StateKeys.PROFILE] = NeedAnalysisProfile().model_dump()

    def fake_update() -> tuple[int | None, list[int]]:
        return 4, []

    monkeypatch.setattr("wizard._update_section_progress", fake_update)

    reran = False

    def fake_rerun() -> None:
        nonlocal reran
        reran = True

    monkeypatch.setattr(st, "rerun", fake_rerun)

    _advance_from_onboarding()

    assert st.session_state[StateKeys.STEP] == 4
    assert not st.session_state.get(StateKeys.PENDING_INCOMPLETE_JUMP, False)
    assert reran
