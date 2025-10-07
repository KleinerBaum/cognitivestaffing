"""Regression tests for summary follow-up regeneration."""

from pathlib import Path
import sys

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from constants.keys import StateKeys
from wizard import _apply_followup_updates


def test_followup_updates_trigger_regeneration(monkeypatch) -> None:
    """Applying follow-up answers regenerates both outputs."""

    st.session_state.clear()
    st.session_state[StateKeys.JOB_AD_SELECTED_VALUES] = {}

    calls: list[str] = []

    def _fake_job_ad(*args, **kwargs) -> bool:
        calls.append("job")
        return True

    def _fake_interview(*args, **kwargs) -> bool:
        calls.append("interview")
        return True

    monkeypatch.setattr("wizard._generate_job_ad_content", _fake_job_ad)
    monkeypatch.setattr(
        "wizard._generate_interview_guide_content", _fake_interview
    )

    data: dict[str, object] = {"company": {}}
    filtered_profile = {"company": {}}
    profile_payload = {
        "requirements": {},
        "responsibilities": {},
        "position": {},
        "company": {},
    }

    job_generated, interview_generated = _apply_followup_updates(
        {"company.name": " ACME "},
        data=data,
        filtered_profile=filtered_profile,
        profile_payload=profile_payload,
        target_value="Generalists",
        manual_entries=[],
        style_reference=None,
        lang="en",
        selected_fields={"company.name"},
        num_questions=5,
        warn_on_length=False,
        show_feedback=False,
    )

    assert calls == ["job", "interview"]
    assert job_generated is True
    assert interview_generated is True
    assert data["company"]["name"] == "ACME"
