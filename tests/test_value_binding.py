from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
import streamlit as st

from constants.keys import ProfilePaths, StateKeys
from state import ensure_state
from wizard._logic import get_value
from wizard.wizard import (
    profile_multiselect,
    profile_selectbox,
    profile_text_input,
)


@pytest.fixture(autouse=True)
def _reset_state() -> Iterator[None]:
    """Provide a clean Streamlit session for every test."""

    st.session_state.clear()
    ensure_state()
    yield
    st.session_state.clear()


def test_get_value_reads_profile_defaults() -> None:
    """``get_value`` should expose values from the profile store."""

    assert get_value(ProfilePaths.COMPANY_NAME) is None

    profile = st.session_state[StateKeys.PROFILE]
    profile["company"]["name"] = "Rheinbahn AG"

    assert get_value(ProfilePaths.COMPANY_NAME) == "Rheinbahn AG"


def test_get_value_supports_default_fallback() -> None:
    """Missing paths should return the provided default sentinel."""

    sentinel = object()
    assert get_value("does.not.exist", default=sentinel) is sentinel


def test_profile_text_input_binds_and_updates_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    """Text inputs should prefill and update the profile via the callback."""

    profile = st.session_state[StateKeys.PROFILE]
    profile["company"]["name"] = "Rheinbahn"

    callbacks: dict[str, Callable[[], None]] = {}

    def fake_text_input(
        label: str,
        *,
        value: str = "",
        key: str | None = None,
        on_change: Callable[[], None] | None = None,
        **_: object,
    ) -> str:
        assert label == "Company"
        assert value == "Rheinbahn"
        assert key == ProfilePaths.COMPANY_NAME
        st.session_state[key] = value
        if on_change is not None:
            callbacks[key] = on_change
        return value

    monkeypatch.setattr(st, "text_input", fake_text_input)

    result = profile_text_input(ProfilePaths.COMPANY_NAME, "Company")
    assert result == "Rheinbahn"

    st.session_state[ProfilePaths.COMPANY_NAME] = "Rheinbahn GmbH"
    callbacks[ProfilePaths.COMPANY_NAME]()

    assert st.session_state[StateKeys.PROFILE]["company"]["name"] == "Rheinbahn GmbH"


def test_profile_selectbox_binds_and_updates_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    """Selectboxes should reflect the profile and write back on change."""

    profile = st.session_state[StateKeys.PROFILE]
    profile["position"]["seniority_level"] = "Senior"

    callbacks: dict[str, Callable[[], None]] = {}
    options = ["Junior", "Mid", "Senior"]

    def fake_selectbox(
        label: str,
        entries: list[str],
        *,
        index: int = 0,
        key: str | None = None,
        on_change: Callable[[], None] | None = None,
        **_: object,
    ) -> str:
        assert label == "Seniority"
        assert entries == options
        assert index == 2
        assert key == ProfilePaths.POSITION_SENIORITY
        selected = entries[index]
        st.session_state[key] = selected
        if on_change is not None:
            callbacks[key] = on_change
        return selected

    monkeypatch.setattr(st, "selectbox", fake_selectbox)

    value = profile_selectbox(ProfilePaths.POSITION_SENIORITY, "Seniority", options)
    assert value == "Senior"

    st.session_state[ProfilePaths.POSITION_SENIORITY] = "Mid"
    callbacks[ProfilePaths.POSITION_SENIORITY]()

    assert st.session_state[StateKeys.PROFILE]["position"]["seniority_level"] == "Mid"


def test_profile_multiselect_binds_and_updates_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    """Multiselect widgets should stay aligned with profile list fields."""

    profile = st.session_state[StateKeys.PROFILE]
    profile["requirements"]["hard_skills_required"] = ["Python", "SQL"]

    callbacks: dict[str, Callable[[], None]] = {}
    options = ["Python", "SQL", "Rust"]

    def fake_multiselect(
        label: str,
        entries: list[str],
        *,
        default: list[str] | None = None,
        key: str | None = None,
        on_change: Callable[[], None] | None = None,
        **_: object,
    ) -> list[str]:
        assert label == "Required skills"
        assert entries == options
        assert default == ["Python", "SQL"]
        assert key == ProfilePaths.REQUIREMENTS_HARD_SKILLS_REQUIRED
        st.session_state[key] = list(default or [])
        if on_change is not None:
            callbacks[key] = on_change
        return list(default or [])

    monkeypatch.setattr(st, "multiselect", fake_multiselect)

    selection = profile_multiselect(
        ProfilePaths.REQUIREMENTS_HARD_SKILLS_REQUIRED,
        "Required skills",
        options,
    )
    assert selection == ["Python", "SQL"]

    st.session_state[ProfilePaths.REQUIREMENTS_HARD_SKILLS_REQUIRED] = ["Python", "Rust"]
    callbacks[ProfilePaths.REQUIREMENTS_HARD_SKILLS_REQUIRED]()

    assert st.session_state[StateKeys.PROFILE]["requirements"]["hard_skills_required"] == [
        "Python",
        "Rust",
    ]
