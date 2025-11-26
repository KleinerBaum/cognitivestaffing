from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

from state.ai_contributions import (
    get_ai_contribution_state,
    record_field_contribution,
    record_list_item_contribution,
    remove_field_contribution,
    remove_list_item_contribution,
)


def test_ai_contribution_state_merges_and_clears() -> None:
    """Field and list contributions record provenance and merge updates."""

    st.session_state.clear()

    first_timestamp = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    record_field_contribution(
        "company.name",
        source="structured_extraction",
        model="gpt-4o-mini",
        timestamp=first_timestamp,
    )

    later_timestamp = datetime(2024, 2, 1, 8, 30, tzinfo=timezone.utc)
    record_field_contribution(
        "company.name",
        source="team_assistant",
        model="o3-mini",
        timestamp=later_timestamp,
    )

    state = get_ai_contribution_state()
    field_entry = state["fields"].get("company.name")
    assert field_entry is not None
    assert field_entry["source"] == "team_assistant"
    assert field_entry["model"] == "o3-mini"
    assert field_entry["timestamp"].startswith("2024-02-01")

    record_list_item_contribution(
        "requirements.hard_skills_required",
        "Python",
        source="skill_assistant",
        model="gpt-4o-mini",
    )
    record_list_item_contribution(
        "requirements.hard_skills_required",
        " python ",
        source="skill_assistant",
        model="gpt-4o-mini",
        timestamp=later_timestamp,
    )
    state = get_ai_contribution_state()
    list_entries = state["items"]["requirements.hard_skills_required"]
    assert set(list_entries.keys()) == {"Python"}
    assert list_entries["Python"]["timestamp"].startswith("2024-02-01")

    remove_list_item_contribution("requirements.hard_skills_required", "Python")
    state = get_ai_contribution_state()
    assert "requirements.hard_skills_required" not in state["items"]

    remove_field_contribution("company.name")
    state = get_ai_contribution_state()
    assert "company.name" not in state["fields"]
