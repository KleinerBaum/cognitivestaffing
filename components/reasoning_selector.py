"""Reasoning level selection component for Streamlit UI."""

from __future__ import annotations

import streamlit as st

from config import REASONING_EFFORT, REASONING_LEVELS
from constants.keys import UIKeys
from utils.i18n import tr

LEVEL_LABELS: dict[str, tuple[str, str]] = {
    "minimal": ("Minimal", "Minimal"),
    "low": ("Niedrig", "Low"),
    "medium": ("Mittel", "Medium"),
    "high": ("Hoch", "High"),
}


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

    level_pairs = [
        (
            value,
            tr(*LEVEL_LABELS.get(value, (value.title(), value.title()))),
        )
        for value in levels
    ]
    value_to_label = dict(level_pairs)
    label_to_value = {label: value for value, label in level_pairs}
    labels = [label for _, label in level_pairs]
    default_label = value_to_label[default]

    stored_label = st.session_state.get(UIKeys.REASONING_SELECT)
    if stored_label in label_to_value:
        selected_index = labels.index(stored_label)
    elif stored_label in levels:
        translated = value_to_label[stored_label]
        st.session_state[UIKeys.REASONING_SELECT] = translated
        selected_index = labels.index(translated)
    else:
        st.session_state[UIKeys.REASONING_SELECT] = default_label
        selected_index = labels.index(default_label)

    selected_label = st.selectbox(
        tr("Denkaufwand", "Reasoning effort"),
        labels,
        index=selected_index,
        key=UIKeys.REASONING_SELECT,
    )
    effort = label_to_value[selected_label]
    st.session_state[key] = effort
    return effort
