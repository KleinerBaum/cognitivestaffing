"""Utility helpers for rendering error messages in Streamlit."""

import streamlit as st


def display_error(msg: str, detail: str | None = None) -> None:
    """Render a user-facing error with optional debug details.

    Args:
        msg: Short error message for the user.
        detail: Optional technical detail shown when debug mode is enabled.
    """
    st.error(msg)
    if detail and st.session_state.get("debug"):
        with st.expander("Details"):
            st.code(detail)
