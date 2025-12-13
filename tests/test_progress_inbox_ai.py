from datetime import datetime, timezone
from typing import Any

import streamlit as st

from core.progress_updates import TodoTask, apply_plan_matches
from models.progress_updates import ProgressUpdateMatch, ProgressUpdatePlan
from state.progress_inbox import apply_inbox_update


def test_apply_plan_matches_updates_tasks() -> None:
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    tasks = [
        TodoTask(
            task_id="outreach",
            title="Candidate outreach",
            description="Send emails",
            progress_target=3,
        ),
        TodoTask(
            task_id="notes",
            title="Notes",
            description="Keep track",
            progress_target=None,
        ),
    ]
    matches = [
        ProgressUpdateMatch(
            todo_id="outreach",
            action="increment_progress",
            amount=2,
            note=None,
            confidence=0.9,
            rationale_short="Matches outreach updates.",
        ),
        ProgressUpdateMatch(
            todo_id="notes",
            action="add_note",
            amount=None,
            note="Manager sync notes",
            confidence=0.8,
            rationale_short="Notes only",
        ),
    ]

    results = apply_plan_matches("Updated tasks", tasks, matches, now=now, event_id="evt-123")

    assert len(results) == 2
    assert tasks[0].progress_current == 2
    assert results[0].action == "increment_progress"
    assert tasks[1].notes[-1].text == "Manager sync notes"
    assert results[1].note_text == "Manager sync notes"


def test_apply_inbox_update_uses_ai_and_event_guard(monkeypatch: Any) -> None:
    st.session_state.clear()

    plan = ProgressUpdatePlan(
        matches=[
            ProgressUpdateMatch(
                todo_id="sourcing",
                action="increment_progress",
                amount=1,
                note=None,
                confidence=0.88,
                rationale_short="Sourcing increment",
            )
        ]
    )

    monkeypatch.setattr("state.progress_inbox.is_llm_enabled", lambda: True)
    monkeypatch.setattr("state.progress_inbox.plan_progress_updates", lambda text, tasks: plan)

    first = apply_inbox_update("Reached out to 1 candidate", event_id="msg-1")
    assert first.used_ai is True
    assert first.results
    assert first.results[0].matched_task is not None
    assert first.results[0].matched_task.progress_current == 1

    second = apply_inbox_update("Reached out to 1 candidate", event_id="msg-1")
    assert second.results == []
    assert second.warning is not None

    st.session_state.clear()
