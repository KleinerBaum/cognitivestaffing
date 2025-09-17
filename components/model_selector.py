"""Model selection component for Streamlit UI."""

from __future__ import annotations

import streamlit as st

from config import GPT5_MINI, GPT5_NANO, OPENAI_MODEL
from constants.keys import UIKeys


def model_selector(key: str = "model") -> str:
    """Render a selectbox to allow users to choose the OpenAI model.

    Args:
        key: Session state key to store the selected model.

    Returns:
        The chosen model identifier.
    """
    option_map = {
        "Automatisch: GPT-5 (empfohlen)": "",
        "Force GPT-5 mini": GPT5_MINI,
        "Force GPT-5 nano": GPT5_NANO,
    }
    override = st.session_state.get("model_override", "")
    default_label = next(
        (label for label, value in option_map.items() if value == override),
        next(iter(option_map)),
    )
    selection = st.selectbox(
        "Basismodell",
        list(option_map.keys()),
        index=list(option_map.keys()).index(default_label),
        key=UIKeys.MODEL_SELECT,
    )
    chosen = option_map[selection]
    st.session_state["model_override"] = chosen
    resolved = chosen or OPENAI_MODEL
    st.session_state[key] = resolved
    st.session_state["model"] = resolved
    if not chosen:
        st.caption(
            "Die App wählt automatisch zwischen GPT-5-mini und GPT-5-nano je nach Aufgabe."
        )
    else:
        st.caption("Override aktiv – alle Aufrufe verwenden das ausgewählte Modell.")
    return resolved
