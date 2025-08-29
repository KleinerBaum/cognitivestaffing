"""Model selection component for Streamlit UI."""

from __future__ import annotations

import streamlit as st

from config import OPENAI_MODEL
from constants.keys import UIKeys


def model_selector(key: str = "model") -> str:
    """Render a selectbox to allow users to choose the OpenAI model.

    Args:
        key: Session state key to store the selected model.

    Returns:
        The chosen model identifier.
    """
    models = [
        "gpt-5-nano",
        "gpt-4.1-nano",
        "gpt-4",
        "gpt-3.5-turbo",
        "gpt-3.5-turbo-16k",
    ]
    default = st.session_state.get(key, OPENAI_MODEL)
    if default not in models:
        models.insert(0, default)
    model = st.selectbox(
        "Model", models, index=models.index(default), key=UIKeys.MODEL_SELECT
    )
    st.session_state[key] = model
    return model
