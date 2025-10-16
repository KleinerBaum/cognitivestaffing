"""Model selection component for Streamlit UI."""

from __future__ import annotations

import streamlit as st

from config import GPT4O, GPT4O_MINI, GPT5_MINI, GPT5_NANO, OPENAI_MODEL, normalise_model_override
from constants.keys import UIKeys
from utils.i18n import tr


def model_selector(key: str = "model") -> str:
    """Render a selectbox to allow users to choose the OpenAI model."""

    option_entries: list[tuple[str | None, str]] = [
        (None, tr("Automatisch: Ausgewogen (empfohlen)", "Auto: Balanced (recommended)")),
        (
            GPT4O,
            tr("GPT-4o (ausgewogen)", "GPT-4o (balanced)"),
        ),
        (
            GPT4O_MINI,
            tr("GPT-4o mini (günstig)", "GPT-4o mini (cost saver)"),
        ),
        (
            GPT5_MINI,
            tr("GPT-5 mini (gpt-5.1-mini) erzwingen", "Force GPT-5 mini (gpt-5.1-mini)"),
        ),
        (
            GPT5_NANO,
            tr("GPT-5 nano (gpt-5.1-nano) erzwingen", "Force GPT-5 nano (gpt-5.1-nano)"),
        ),
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
                "Auto-Routing nutzt GPT-4o für komplexe Aufgaben und GPT-4o mini für günstige Antworten.",
                "Auto routing uses GPT-4o for complex tasks and GPT-4o mini for cost-efficient replies.",
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
