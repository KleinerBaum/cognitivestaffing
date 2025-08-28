"""Model selection component for Streamlit UI."""

from __future__ import annotations

import streamlit as st

from config import OPENAI_MODEL


def model_selector(key: str = "llm_model") -> str:
    """Render a selectbox to allow users to choose the OpenAI model.

    Args:
        key: Session state key to store the selected model.

    Returns:
        The chosen model identifier.
    """
    models = ["gpt-5-nano", "gpt-4.1-nano"]
    default = st.session_state.get(key, OPENAI_MODEL)
    if default not in models:
        default = models[0]
    model = st.selectbox("Model", models, index=models.index(default))
    st.session_state[key] = model
    return model
