"""Verbosity level selector component for Streamlit UI."""

from __future__ import annotations

import streamlit as st

from config import VERBOSITY, VERBOSITY_LEVELS, normalise_verbosity
from constants.keys import UIKeys
from utils.i18n import tr


def _label_for_level(level: str) -> str:
    """Return a translated label for ``level``."""

    match level:
        case "low":
            return tr("Kompakt (kostensparend)", "Concise (cost-saving)")
        case "medium":
            return tr("Standard", "Standard")
        case "high":
            return tr("Ausführlich", "Detailed")
        case _:
            return level.title()


def verbosity_selector(key: str = "verbosity") -> str:
    """Render a selectbox to choose the chat response verbosity."""

    levels = list(VERBOSITY_LEVELS)
    default = normalise_verbosity(st.session_state.get(key), default=VERBOSITY)
    try:
        default_index = levels.index(default)
    except ValueError:
        default_index = levels.index(VERBOSITY)

    entries = [(level, _label_for_level(level)) for level in levels]
    selection = st.selectbox(
        tr("Antwort-Detailgrad", "Response verbosity"),
        [label for _, label in entries],
        index=default_index,
        key=UIKeys.VERBOSITY_SELECT,
    )
    selected_value = next(value for value, label in entries if label == selection)
    st.session_state[key] = selected_value
    return selected_value
