from core.schema import coerce_and_fill
from core.ss_bridge import from_session_state, to_session_state


def test_round_trip_session_state():
    profile = coerce_and_fill(
        {
            "position": {"job_title": "Dev"},
            "responsibilities": {"items": ["Code", "Review"]},
            "requirements": {"languages_required": ["EN", "DE"]},
            "location": {},
            "employment": {},
            "compensation": {},
            "process": {},
            "meta": {},
        }
    )
    ss = {}
    to_session_state(profile, ss)
    profile2 = from_session_state(ss)
    assert profile2 == profile
    assert ss["responsibilities.items"] == "Code\nReview"
