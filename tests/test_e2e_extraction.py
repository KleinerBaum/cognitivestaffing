import openai_utils
from core.ss_bridge import to_session_state
from models.need_analysis import NeedAnalysisProfile


def test_e2e_to_session_state(monkeypatch) -> None:
    """End-to-end extraction should populate session state."""

    class _Result:
        def __init__(self, data: dict) -> None:
            self.data = data

    def fake_extract_with_function(text: str, schema: dict, model=None, **kwargs):
        return _Result({"position": {"job_title": "Dev"}})

    monkeypatch.setattr(
        openai_utils, "extract_with_function", fake_extract_with_function
    )
    profile_result = openai_utils.extract_with_function("input", {})
    profile = NeedAnalysisProfile.model_validate(profile_result.data)
    ss: dict = {}
    to_session_state(profile, ss)
    assert ss["position.job_title"] == "Dev"
