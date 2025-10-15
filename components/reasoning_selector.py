"""Reasoning level selection component for Streamlit UI."""

from __future__ import annotations

import streamlit as st

from config import REASONING_EFFORT, REASONING_LEVELS
from constants.keys import UIKeys


def reasoning_selector(key: str = "reasoning_effort") -> str:
    """Render a selectbox to choose model reasoning effort.

    Args:
        key: Session key to store the selected reasoning level.

    Returns:
        The selected reasoning effort level.
    """
    levels = list(REASONING_LEVELS)
    default = st.session_state.get(key, REASONING_EFFORT)
    if isinstance(default, str):
        default = default.lower()
    if default not in levels:
        default = "medium"
    effort = st.selectbox(
        "Reasoning Effort",
        levels,
        index=levels.index(default),
        key=UIKeys.REASONING_SELECT,
    )
    st.session_state[key] = effort
    return effort
