"""Simple progress stepper for wizard navigation."""

from __future__ import annotations

import streamlit as st


def render_stepper(current: int, total: int) -> None:
    """Render a progress bar indicating wizard progress.

    Args:
        current: Current step index (0-based).
        total: Total number of steps.
    """

    if total <= 0:
        return
    st.progress((current + 1) / total)
