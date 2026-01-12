from __future__ import annotations

import streamlit as st

from constants.flow_mode import FlowMode
from constants.keys import StateKeys
from state.ensure_state import ensure_state


def test_flow_mode_defaults_to_single_page() -> None:
    st.session_state.clear()

    ensure_state()

    assert st.session_state[StateKeys.FLOW_MODE] == FlowMode.SINGLE_PAGE


def test_flow_mode_persists_across_reruns() -> None:
    st.session_state.clear()

    ensure_state()
    st.session_state[StateKeys.FLOW_MODE] = FlowMode.SINGLE_PAGE

    ensure_state()

    assert st.session_state[StateKeys.FLOW_MODE] == FlowMode.SINGLE_PAGE
