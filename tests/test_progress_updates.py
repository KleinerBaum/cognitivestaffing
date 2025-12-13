from datetime import datetime, timezone

from core.progress_updates import (
    TodoTask,
    apply_progress_update,
    match_task,
    parse_progress_delta,
)


_DEF_TASKS = [
    TodoTask(
        task_id="outreach",
        title="Candidate outreach",
        description="Send personalised outreach emails to leads",
        progress_target=5,
    ),
    TodoTask(
        task_id="screening",
        title="Application screening",
        description="Screen inbound applications",
        progress_target=3,
    ),
    TodoTask(
        task_id="notes",
        title="Hiring manager sync",
        description="Capture takeaways from hiring manager calls",
        progress_target=None,
    ),
]


def _fresh_tasks() -> list[TodoTask]:
    return [
        TodoTask(
            task_id=task.task_id,
            title=task.title,
            description=task.description,
            progress_current=task.progress_current,
            progress_target=task.progress_target,
            notes=list(task.notes),
        )
        for task in _DEF_TASKS
    ]


def test_matching_prefers_relevant_task() -> None:
    tasks = _fresh_tasks()
    result = match_task("Sent outreach emails to four leads", tasks, threshold=0.1)
    assert result.matched_task is not None
    assert result.matched_task.task_id == "outreach"


def test_apply_progress_update_increments_with_number() -> None:
    tasks = _fresh_tasks()
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    result = apply_progress_update("Followed up with +2 outreach emails", tasks, threshold=0.1, now=now)
    assert result.updated is True
    assert result.matched_task is not None
    assert result.matched_task.progress_current == 2
    assert result.progress_delta == 2


def test_apply_progress_update_adds_note_when_no_target() -> None:
    tasks = _fresh_tasks()
    result = apply_progress_update("Shared notes from the hiring manager chat", tasks, threshold=0.1)
    assert result.updated is True
    note_task = next(task for task in tasks if task.task_id == "notes")
    assert len(note_task.notes) == 1
    assert "hiring manager" in note_task.notes[0].text


def test_parse_progress_delta_understands_variations() -> None:
    assert parse_progress_delta("+3 follow-ups done") == 3
    assert parse_progress_delta("2 Bewerbungen gescreent") == 2
    assert parse_progress_delta("4x calls") == 4
