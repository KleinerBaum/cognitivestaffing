import openai_utils
from core.ss_bridge import to_session_state
from models.need_analysis import NeedAnalysisProfile


def test_e2e_to_session_state(monkeypatch) -> None:
    """End-to-end extraction should populate session state."""

    def fake_extract_with_function(text: str, schema: dict, model=None):
        return {"position": {"job_title": "Dev"}}

    monkeypatch.setattr(
        openai_utils, "extract_with_function", fake_extract_with_function
    )
    jd_dict = openai_utils.extract_with_function("input", {})
    jd = NeedAnalysisProfile.model_validate(jd_dict)
    ss: dict = {}
    to_session_state(jd, ss)
    assert ss["position.job_title"] == "Dev"
