from typing import Any, Callable, Dict

import streamlit as st

from constants.keys import StateKeys, UIKeys

__all__ = [
    "UIKeys",
    "StateKeys",
    "bootstrap_session",
    "bind_textarea",
    "migrate_legacy_keys",
]


DEFAULTS: Dict[str, Any] = {
    StateKeys.RAW_TEXT: "",
    StateKeys.PROFILE: {},
    StateKeys.STEP: 0,
}


def bootstrap_session() -> None:
    """Initialize state keys before any widget is created."""
    for k, v in DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v


def bind_textarea(
    label: str,
    ui_key: str,
    data_key: str,
    placeholder: str = "",
    help: str | None = None,
    on_change: Callable[[], None] | None = None,
) -> None:
    """Render a text area bound to a state key.

    The UI key mirrors the data key only on first run; subsequent updates go
    through the `on_change` callback.
    """

    if ui_key not in st.session_state:
        st.session_state[ui_key] = st.session_state.get(data_key, "")

    def _on_change() -> None:
        st.session_state[data_key] = st.session_state[ui_key]
        if on_change is not None:
            on_change()

    value = st.text_area(
        label,
        key=ui_key,
        placeholder=placeholder,
        help=help,
        on_change=_on_change,
    )

    current_value = st.session_state.get(ui_key, value)
    if st.session_state.get(data_key) != current_value:
        st.session_state[data_key] = current_value
        if on_change is not None:
            on_change()


def migrate_legacy_keys() -> None:
    """Migrate legacy session keys for backward compatibility.

    Older versions stored widget and data values under plain keys like
    ``jd_text`` or nested structures such as ``data.jd_text``. Later revisions
    renamed ``jd_raw_text`` to ``profile_raw_text``. Newer releases use flat,
    descriptive keys defined in :class:`StateKeys`. This function promotes old
    keys to their new counterparts and removes the deprecated entries to prevent
    collisions.
    """

    ss = st.session_state

    # --- Data key migrations ---
    if "jd_text" in ss and not ss.get(StateKeys.RAW_TEXT):
        ss[StateKeys.RAW_TEXT] = ss["jd_text"]
    if "data.jd_text" in ss and not ss.get(StateKeys.RAW_TEXT):
        ss[StateKeys.RAW_TEXT] = ss["data.jd_text"]
    if "jd_raw_text" in ss and not ss.get(StateKeys.RAW_TEXT):
        ss[StateKeys.RAW_TEXT] = ss["jd_raw_text"]
    ss.pop("jd_text", None)
    ss.pop("data.jd_text", None)
    ss.pop("jd_raw_text", None)

    if "data.profile" in ss and not ss.get(StateKeys.PROFILE):
        ss[StateKeys.PROFILE] = ss["data.profile"]
    if "data" in ss and not ss.get(StateKeys.PROFILE):
        ss[StateKeys.PROFILE] = ss["data"]
    ss.pop("data.profile", None)
    ss.pop("data", None)

    if "step" in ss and StateKeys.STEP not in ss:
        ss[StateKeys.STEP] = ss["step"]
    if "data.step" in ss and StateKeys.STEP not in ss:
        ss[StateKeys.STEP] = ss["data.step"]
    ss.pop("step", None)
    ss.pop("data.step", None)

    if "usage" in ss and StateKeys.USAGE not in ss:
        ss[StateKeys.USAGE] = ss["usage"]
    ss.pop("usage", None)
    if StateKeys.USAGE in ss and isinstance(ss[StateKeys.USAGE], dict):
        usage_state = ss[StateKeys.USAGE]
        usage_state.setdefault("input_tokens", 0)
        usage_state.setdefault("output_tokens", 0)
        usage_state.setdefault("by_task", {})

    # --- UI key migrations ---
    legacy_ui_map: Dict[str, str] = {
        "ui.jd_text_input": UIKeys.PROFILE_TEXT_INPUT,
        "ui.jd_file_uploader": UIKeys.PROFILE_FILE_UPLOADER,
        "ui.jd_url_input": UIKeys.PROFILE_URL_INPUT,
        "jd_text_input": UIKeys.PROFILE_TEXT_INPUT,
        "jd_file_uploader": UIKeys.PROFILE_FILE_UPLOADER,
        "jd_url_input": UIKeys.PROFILE_URL_INPUT,
    }
    for old, new in legacy_ui_map.items():
        if old in ss and old.startswith("ui."):
            ss[new] = ss[old]
        elif old in ss and not ss.get(new):
            ss[new] = ss[old]
        ss.pop(old, None)
