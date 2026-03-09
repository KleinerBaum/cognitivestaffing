import streamlit as st

from constants.keys import StateKeys, UIKeys
from utils.session import bootstrap_session, migrate_legacy_keys
from wizard.navigation.state import bootstrap_navigation_state, get_current_step_key


def test_migrate_legacy_profile_text() -> None:
    """Legacy ``jd_text`` key is moved to ``profile_raw_text``."""
    st.session_state.clear()
    st.session_state["jd_text"] = "legacy"
    bootstrap_session()
    migrate_legacy_keys()
    assert st.session_state.get(StateKeys.RAW_TEXT) == "legacy"
    assert "jd_text" not in st.session_state


def test_migrate_jd_raw_text_alias() -> None:
    """Existing ``jd_raw_text`` key is migrated to ``profile_raw_text``."""
    st.session_state.clear()
    st.session_state["jd_raw_text"] = "legacy"
    bootstrap_session()
    migrate_legacy_keys()
    assert st.session_state.get(StateKeys.RAW_TEXT) == "legacy"
    assert "jd_raw_text" not in st.session_state


def test_migrate_legacy_ui_keys() -> None:
    """Legacy UI keys are promoted to namespaced ``ui.*`` variants."""
    st.session_state.clear()
    st.session_state["jd_text_input"] = "txt"
    st.session_state["jd_file_uploader"] = object()
    st.session_state["jd_url_input"] = "https://example.com"
    st.session_state["ui.jd_text_input"] = "txt2"
    st.session_state["ui.jd_file_uploader"] = object()
    st.session_state["ui.jd_url_input"] = "https://example.org"
    bootstrap_session()
    migrate_legacy_keys()
    assert st.session_state.get(UIKeys.PROFILE_TEXT_INPUT) == "txt2"
    assert st.session_state.get(UIKeys.PROFILE_FILE_UPLOADER) is not None
    assert st.session_state.get(UIKeys.PROFILE_URL_INPUT) == "https://example.org"
    assert "jd_text_input" not in st.session_state
    assert "jd_file_uploader" not in st.session_state
    assert "jd_url_input" not in st.session_state
    assert "ui.jd_text_input" not in st.session_state
    assert "ui.jd_file_uploader" not in st.session_state
    assert "ui.jd_url_input" not in st.session_state


def test_bootstrap_navigation_state_migrates_legacy_payload_once() -> None:
    st.session_state.clear()
    st.session_state["wizard"] = {"current_step": "company", "history": ["jobad", "company"]}
    st.session_state[StateKeys.STEP] = 5
    query_params: dict[str, object] = {}

    bootstrap_navigation_state(
        session_state=st.session_state,
        query_params=query_params,
        wizard_id="default",
        active_step_keys=("jobad", "company", "skills"),
        default_step_key="jobad",
        legacy_index_to_key={0: "jobad", 1: "company", 5: "skills"},
    )

    assert (
        get_current_step_key(session_state=st.session_state, wizard_id="default", default_step_key="jobad") == "company"
    )
    assert query_params["step"] == "company"

    st.session_state["wizard"] = {"current_step": "skills"}
    bootstrap_navigation_state(
        session_state=st.session_state,
        query_params=query_params,
        wizard_id="default",
        active_step_keys=("jobad", "company", "skills"),
        default_step_key="jobad",
        legacy_index_to_key={0: "jobad", 1: "company", 5: "skills"},
    )

    assert (
        get_current_step_key(session_state=st.session_state, wizard_id="default", default_step_key="jobad") == "company"
    )
