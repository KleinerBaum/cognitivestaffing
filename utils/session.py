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
    """Migrate legacy session keys for backward compatibility.

    Older versions stored widget and data values under plain keys like
    ``jd_text`` or ``jd_text_input``.  Newer releases namespace these keys under
    ``data.*`` for business data and ``ui.*`` for widget "shadow" keys.  This
    function promotes old keys to their new counterparts and removes the
    deprecated entries to prevent collisions.
    """

    ss = st.session_state

    # --- Data key migration ---
    if "jd_text" in ss and not ss.get(DataKeys.JD_TEXT):
        ss[DataKeys.JD_TEXT] = ss["jd_text"]
    ss.pop("jd_text", None)

    # --- UI key migrations ---
    legacy_ui_map: Dict[str, str] = {
        "jd_text_input": UIKeys.JD_TEXT_INPUT,
        "jd_file_uploader": UIKeys.JD_FILE_UPLOADER,
        "jd_url_input": UIKeys.JD_URL_INPUT,
    }
    for old, new in legacy_ui_map.items():
        if old in ss and not ss.get(new):
            ss[new] = ss[old]
        ss.pop(old, None)
