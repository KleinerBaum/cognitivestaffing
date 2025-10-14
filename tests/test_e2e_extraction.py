from typing import Any

import openai_utils
from core.ss_bridge import from_session_state, to_session_state
from models.need_analysis import NeedAnalysisProfile


def test_e2e_to_session_state(monkeypatch) -> None:
    """End-to-end extraction should populate session state."""

    class _Result:
        def __init__(self, data: dict) -> None:
            self.data = data

    def fake_extract_with_function(text: str, schema: dict, model=None, **kwargs):
        return _Result({"position": {"job_title": "Dev"}})

    monkeypatch.setattr(openai_utils, "extract_with_function", fake_extract_with_function)
    profile_result = openai_utils.extract_with_function("input", {})
    profile = NeedAnalysisProfile.model_validate(profile_result.data)
    ss: dict = {}
    to_session_state(profile, ss)
    assert ss["position.job_title"] == "Dev"


def test_e2e_roundtrip_preserves_skills() -> None:
    """Extraction bridge should keep list fields intact across round-trips."""

    base: dict[str, Any] = NeedAnalysisProfile().model_dump()
    base["position"]["job_title"] = "Data Engineer"
    base["requirements"]["hard_skills_required"] = ["Python", "SQL"]
    base["requirements"]["soft_skills_required"] = ["Collaboration"]
    profile = NeedAnalysisProfile.model_validate(base)

    session: dict[str, Any] = {}
    to_session_state(profile, session)

    assert session["requirements.hard_skills_required"] == "Python\nSQL"
    assert session["requirements.soft_skills_required"] == "Collaboration"

    restored = from_session_state(session)
    assert restored.position.job_title == "Data Engineer"
    assert restored.requirements.hard_skills_required == ["Python", "SQL"]
    assert restored.requirements.soft_skills_required == ["Collaboration"]
