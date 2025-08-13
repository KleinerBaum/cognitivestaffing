from core.schema import coerce_and_fill
from core.ss_bridge import from_session_state, to_session_state


def test_round_trip_session_state():
    jd = coerce_and_fill(
        {
            "position": {"job_title": "Dev"},
            "responsibilities": {"items": ["Code", "Review"]},
            "requirements": {"languages_required": ["EN", "DE"]},
        }
    )
    ss = {}
    to_session_state(jd, ss)
    jd2 = from_session_state(ss)
    assert jd2 == jd
    assert ss["responsibilities.items"] == "Code\nReview"


def test_alias_fields_round_trip():
    ss = {"tasks": "Alpha\nBeta", "contract_type": "Part-time"}
    jd = from_session_state(ss)
    assert jd.responsibilities.items == ["Alpha", "Beta"]
    assert jd.employment.job_type == "Part-time"
    to_session_state(jd, ss)
    assert "tasks" not in ss
    assert "contract_type" not in ss
