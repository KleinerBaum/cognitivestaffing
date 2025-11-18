from __future__ import annotations

from typing import Any

import pytest
import streamlit as st

from constants.keys import ProfilePaths, StateKeys
import wizard


@pytest.fixture(autouse=True)
def _clear_session_state() -> None:
    st.session_state.clear()
    yield
    st.session_state.clear()


def _base_requirements_profile() -> dict[str, Any]:
    return {
        "requirements": {
            "hard_skills_required": ["Python"],
            "hard_skills_optional": ["Go"],
            "soft_skills_required": ["Communication"],
            "soft_skills_optional": ["Mentoring"],
            "tools_and_technologies": ["Streamlit"],
            "languages_required": ["English"],
            "languages_optional": ["German"],
            "certificates": ["AWS"],
            "certifications": ["AWS"],
            "background_check_required": False,
            "reference_check_required": True,
            "portfolio_required": False,
        }
    }


def test_summary_requirements_mirrors_compliance_toggles(monkeypatch: pytest.MonkeyPatch) -> None:
    profile = _base_requirements_profile()
    st.session_state[StateKeys.PROFILE] = profile
    st.session_state[StateKeys.ESCO_MISSING_SKILLS] = []
    st.session_state["lang"] = "en"

    checkbox_calls: list[dict[str, Any]] = []
    checkbox_values = {
        str(ProfilePaths.REQUIREMENTS_BACKGROUND_CHECK_REQUIRED): True,
        str(ProfilePaths.REQUIREMENTS_REFERENCE_CHECK_REQUIRED): False,
        str(ProfilePaths.REQUIREMENTS_PORTFOLIO_REQUIRED): True,
    }

    def fake_checkbox(label: str, *, value: bool, key: str | None, help: str | None, **_: Any) -> bool:
        checkbox_calls.append(
            {
                "label": label,
                "help": help,
                "value": value,
                "key": key,
            }
        )
        assert key in checkbox_values
        return checkbox_values[key]

    def fake_text_area(_label: str, *, value: str, **__: Any) -> str:
        return value

    caption_messages: list[str] = []

    def record_caption(message: str, *_, **__: Any) -> None:
        caption_messages.append(message)

    monkeypatch.setattr(st, "checkbox", fake_checkbox)
    monkeypatch.setattr(st, "text_area", fake_text_area)
    monkeypatch.setattr(st, "info", lambda *_, **__: None)
    monkeypatch.setattr(st, "caption", record_caption)

    update_calls: list[tuple[str, Any]] = []

    def record_update(path: str, value: Any, **__: Any) -> None:
        update_calls.append((path, value))

    monkeypatch.setattr("wizard.flow._update_profile", record_update)

    wizard._summary_requirements()

    labels = {call["label"] for call in checkbox_calls}
    assert "Background check required" in labels
    assert "Reference check required" in labels
    assert "Portfolio / work samples required" in labels
    assert any("Skills & Requirements" in message for message in caption_messages)

    expected_updates = {
        ProfilePaths.REQUIREMENTS_BACKGROUND_CHECK_REQUIRED: True,
        ProfilePaths.REQUIREMENTS_REFERENCE_CHECK_REQUIRED: False,
        ProfilePaths.REQUIREMENTS_PORTFOLIO_REQUIRED: True,
    }
    recorded = {path: value for path, value in update_calls if path in expected_updates}
    assert recorded == expected_updates

    requirements = st.session_state[StateKeys.PROFILE]["requirements"]
    assert requirements["background_check_required"] is True
    assert requirements["reference_check_required"] is False
    assert requirements["portfolio_required"] is True
