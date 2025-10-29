from __future__ import annotations

from collections.abc import Iterator

import pytest
import streamlit as st

from constants.keys import ProfilePaths, StateKeys
from state import ensure_state
from wizard._logic import _update_profile, get_value


@pytest.fixture(autouse=True)
def _reset_state() -> Iterator[None]:
    """Provide a clean Streamlit session for the binding migration tests."""

    st.session_state.clear()
    yield
    st.session_state.clear()


def test_get_value_and_update_profile() -> None:
    """Legacy session keys should migrate to canonical paths and stay synced."""

    st.session_state["company_name"] = "ACME GmbH"
    ensure_state()

    assert "company_name" not in st.session_state
    assert get_value(ProfilePaths.COMPANY_NAME) == "ACME GmbH"
    profile = st.session_state[StateKeys.PROFILE]
    assert profile["company"]["name"] == "ACME GmbH"

    _update_profile(ProfilePaths.COMPANY_NAME, "ACME Ventures")

    assert get_value(ProfilePaths.COMPANY_NAME) == "ACME Ventures"
    assert st.session_state[StateKeys.PROFILE]["company"]["name"] == "ACME Ventures"
    assert st.session_state[ProfilePaths.COMPANY_NAME] == "ACME Ventures"
