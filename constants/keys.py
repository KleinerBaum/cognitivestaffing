class UIKeys:
    """Keys for UI widgets in ``st.session_state``."""

    JD_TEXT_INPUT = "ui.jd_text_input"
    JD_FILE_UPLOADER = "ui.jd_file_uploader"
    JD_URL_INPUT = "ui.jd_url_input"
    LANG_SELECT = "ui.lang_select"
    MODEL_SELECT = "ui.model_select"
    REASONING_SELECT = "ui.reasoning_select"
    TONE_SELECT = "ui.summary.tone"
    NUM_QUESTIONS = "ui.summary.num_questions"
    AUDIENCE_SELECT = "ui.summary.audience"
    JOB_AD_FEEDBACK = "ui.job_ad.feedback"
    REFINE_JOB_AD = "ui.job_ad.refine"


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
    BENEFIT_SUGGESTIONS = "benefit_suggestions"
    EXTRACTION_SUMMARY = "extraction_summary"
    EXTRACTION_MISSING = "extraction_missing"
    BIAS_FINDINGS = "data.bias_findings"
