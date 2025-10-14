"""Model selection component for Streamlit UI."""

from __future__ import annotations

import streamlit as st

from config import GPT5_MINI, GPT5_NANO, OPENAI_MODEL, normalise_model_override
from constants.keys import UIKeys
from utils.i18n import tr


def model_selector(key: str = "model") -> str:
    """Render a selectbox to allow users to choose the OpenAI model."""

    option_entries: list[tuple[str | None, str]] = [
        (None, tr("Automatisch: GPT-5 (empfohlen)", "Auto: GPT-5 (recommended)")),
        (GPT5_MINI, tr("GPT-5 mini erzwingen", "Force GPT-5 mini")),
        (GPT5_NANO, tr("GPT-5 nano erzwingen", "Force GPT-5 nano")),
    ]

    raw_override = st.session_state.get("model_override", "")
    current_override = normalise_model_override(raw_override)
    default_index = 0
    if current_override:
        current_lower = current_override.lower()
        for idx, (value, _) in enumerate(option_entries):
            if value and value.lower() == current_lower:
                default_index = idx
                break

    labels = [label for _, label in option_entries]
    selection = st.selectbox(
        tr("Basismodell", "Base model"),
        labels,
        index=default_index,
        key=UIKeys.MODEL_SELECT,
    )

    selected_value = next(value for value, label in option_entries if label == selection)
    normalised_value = normalise_model_override(selected_value) if selected_value else None

    if normalised_value is None:
        st.session_state["model_override"] = ""
        resolved = OPENAI_MODEL
        st.caption(
            tr(
                "Die App wählt automatisch zwischen GPT-5-mini und GPT-5-nano je nach Aufgabe.",
                "The app automatically chooses between GPT-5 mini and GPT-5 nano per task.",
            )
        )
    else:
        st.session_state["model_override"] = normalised_value
        resolved = normalised_value
        st.caption(
            tr(
                "Override aktiv – alle Aufrufe verwenden das ausgewählte Modell.",
                "Override active – all calls use the selected model.",
            )
        )

    st.session_state[key] = resolved
    st.session_state["model"] = resolved
    return resolved
