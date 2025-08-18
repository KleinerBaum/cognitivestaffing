from typing import Any, Dict
import streamlit as st

from config import DataKeys, UIKeys

__all__ = [
    "UIKeys",
    "DataKeys",
    "bootstrap_session",
    "bind_textarea",
    "migrate_legacy_keys",
]


DEFAULTS: Dict[str, Any] = {
    DataKeys.JD_TEXT: "",
    DataKeys.PROFILE: {},
    DataKeys.STEP: 0,
}


def bootstrap_session() -> None:
    """Initialize data keys before any widget is created."""
    for k, v in DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v


def bind_textarea(
    label: str, ui_key: str, data_key: str, placeholder: str = ""
) -> None:
    """Render a text area bound to a data key.

    The UI key mirrors the data key only on first run; subsequent updates go
    through the `on_change` callback.
    """

    if ui_key not in st.session_state:
        st.session_state[ui_key] = st.session_state.get(data_key, "")

    def _on_change() -> None:
        st.session_state[data_key] = st.session_state[ui_key]

    st.text_area(label, key=ui_key, placeholder=placeholder, on_change=_on_change)


def migrate_legacy_keys() -> None:
    """Migrate legacy session keys for backward compatibility."""
    if "jd_text" in st.session_state and DataKeys.JD_TEXT not in st.session_state:
        st.session_state[DataKeys.JD_TEXT] = st.session_state["jd_text"]
        try:
            del st.session_state["jd_text"]
        except Exception:  # pragma: no cover - defensive
            pass
