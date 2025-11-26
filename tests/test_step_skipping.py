import streamlit as st

from state.ai_failures import (
    AI_FAILURE_THRESHOLD,
    get_failure_count,
    get_skipped_steps,
    increment_step_failure,
    is_step_ai_skipped,
    mark_step_ai_skipped,
    reset_step_failures,
    should_offer_skip,
)


def test_failure_tracking_and_skip_flag_behavior() -> None:
    st.session_state.clear()

    assert get_failure_count("team") == 0
    assert not should_offer_skip("team")

    increment_step_failure("team")
    assert get_failure_count("team") == 1
    assert not should_offer_skip("team")

    increment_step_failure("team")
    assert get_failure_count("team") == AI_FAILURE_THRESHOLD
    assert should_offer_skip("team")

    mark_step_ai_skipped("team")
    assert is_step_ai_skipped("team")
    assert "team" in get_skipped_steps()
    assert not should_offer_skip("team")

    reset_step_failures("team")
    assert get_failure_count("team") == 0
    assert is_step_ai_skipped("team")
