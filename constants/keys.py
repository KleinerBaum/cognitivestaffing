class UIKeys:
    """Keys for UI widgets in ``st.session_state``."""

    JD_TEXT_INPUT = "ui.jd_text_input"
    JD_FILE_UPLOADER = "ui.jd_file_uploader"
    JD_URL_INPUT = "ui.jd_url_input"
    LANG_SELECT = "ui.lang_select"


class StateKeys:
    """Keys for data stored in ``st.session_state``."""

    PROFILE = "profile_data"
    RAW_TEXT = "jd_raw_text"
    STEP = "current_step"
    FOLLOWUPS = "followup_questions"
    USAGE = "api_usage"
    JOB_AD_MD = "data.job_ad_md"
    BOOLEAN_STR = "data.boolean_str"
    INTERVIEW_GUIDE_MD = "data.interview_md"
    SKILL_SUGGESTIONS = "skill_suggestions"
    EXTRACTION_SUMMARY = "extraction_summary"
