import streamlit as st

from utils.session import bootstrap_session, migrate_legacy_keys, DataKeys, UIKeys


def test_migrate_legacy_jd_text() -> None:
    """Legacy ``jd_text`` key is moved to ``data.jd_text``."""
    st.session_state.clear()
    st.session_state["jd_text"] = "legacy"
    bootstrap_session()
    migrate_legacy_keys()
    assert st.session_state.get(DataKeys.JD_TEXT) == "legacy"
    assert "jd_text" not in st.session_state


def test_migrate_legacy_ui_keys() -> None:
    """Legacy UI keys are promoted to namespaced ``ui.*`` variants."""
    st.session_state.clear()
    st.session_state["jd_text_input"] = "txt"
    st.session_state["jd_file_uploader"] = object()
    st.session_state["jd_url_input"] = "https://example.com"
    bootstrap_session()
    migrate_legacy_keys()
    assert st.session_state.get(UIKeys.JD_TEXT_INPUT) == "txt"
    assert st.session_state.get(UIKeys.JD_FILE_UPLOADER) is not None
    assert st.session_state.get(UIKeys.JD_URL_INPUT) == "https://example.com"
    assert "jd_text_input" not in st.session_state
    assert "jd_file_uploader" not in st.session_state
    assert "jd_url_input" not in st.session_state
