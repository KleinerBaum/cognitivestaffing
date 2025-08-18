class UIKeys:
    """Keys for UI widgets in ``st.session_state``."""

    JD_TEXT_INPUT = "ui.jd_text_input"
    JD_FILE_UPLOADER = "ui.jd_file_uploader"
    JD_URL_INPUT = "ui.jd_url_input"


class StateKeys:
    """Keys for data stored in ``st.session_state``."""

    PROFILE = "profile_data"
    RAW_TEXT = "jd_raw_text"
    STEP = "current_step"
    FOLLOWUPS = "followup_questions"
    USAGE = "api_usage"
