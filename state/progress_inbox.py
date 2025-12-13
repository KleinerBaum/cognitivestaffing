from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import streamlit as st

from config import is_llm_enabled
from core.progress_updates import (
    ProgressUpdateResult,
    TodoNote,
    TodoTask,
    apply_plan_matches,
    apply_progress_update,
)
from llm.progress_inbox import ProgressPlannerError, plan_progress_updates
from models.progress_updates import ProgressUpdatePlan

_TASK_STATE_KEY = "progress_inbox.tasks"
_EVENT_STATE_KEY = "progress_inbox.processed_events"


@dataclass(slots=True)
class ProgressInboxResult:
    results: list[ProgressUpdateResult]
    used_ai: bool = False
    warning: str | None = None
    event_id: str | None = None


def _default_tasks() -> list[TodoTask]:
    """Return a small set of demo tasks for the progress inbox."""

    return [
        TodoTask(
            task_id="sourcing",
            title="Candidate outreach",
            description="Send personalised outreach emails to target profiles.",
            progress_current=0,
            progress_target=5,
        ),
        TodoTask(
            task_id="screening",
            title="Application screening",
            description="Review inbound applications and shortlist strong fits.",
            progress_current=1,
            progress_target=8,
        ),
        TodoTask(
            task_id="notes",
            title="Hiring manager sync",
            description="Capture notes from hiring manager check-ins.",
            progress_current=0,
            progress_target=None,
        ),
    ]


def _serialise_task(task: TodoTask) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "title": task.title,
        "description": task.description,
        "progress_current": task.progress_current,
        "progress_target": task.progress_target,
        "notes": [{"text": note.text, "created_at": note.created_at.isoformat()} for note in task.notes],
    }


def _deserialise_task(payload: Mapping[str, Any]) -> TodoTask:
    notes_payload = payload.get("notes") or []
    notes: list[TodoNote] = []
    for raw in notes_payload:
        if not isinstance(raw, Mapping):
            continue
        created_at_raw = raw.get("created_at")
        try:
            created_at = (
                datetime.fromisoformat(created_at_raw)
                if isinstance(created_at_raw, str)
                else datetime.now(timezone.utc)
            )
        except ValueError:
            created_at = datetime.now(timezone.utc)
        notes.append(TodoNote(text=str(raw.get("text", "")), created_at=created_at))
    target_raw = payload.get("progress_target")
    progress_target: int | None
    if isinstance(target_raw, (int, float)):
        progress_target = int(target_raw)
    elif isinstance(target_raw, str) and target_raw.strip().isdigit():
        progress_target = int(target_raw.strip())
    else:
        progress_target = None
    return TodoTask(
        task_id=str(payload.get("task_id", "")),
        title=str(payload.get("title", "")),
        description=str(payload.get("description", "")),
        progress_current=int(payload.get("progress_current") or 0),
        progress_target=progress_target,
        notes=notes,
    )


def _ensure_tasks() -> list[TodoTask]:
    stored = st.session_state.get(_TASK_STATE_KEY)
    if not stored:
        tasks = _default_tasks()
        st.session_state[_TASK_STATE_KEY] = [_serialise_task(task) for task in tasks]
        return tasks

    if isinstance(stored, Iterable):
        tasks = []
        for item in stored:
            if isinstance(item, Mapping):
                tasks.append(_deserialise_task(item))
        if tasks:
            return tasks
    tasks = _default_tasks()
    st.session_state[_TASK_STATE_KEY] = [_serialise_task(task) for task in tasks]
    return tasks


def _get_processed_event_ids() -> set[str]:
    events: set[str] = set()
    stored = st.session_state.get(_EVENT_STATE_KEY)
    if isinstance(stored, Iterable):
        for entry in stored:
            if isinstance(entry, str) and entry.strip():
                events.add(entry.strip())
    return events


def _store_processed_event_ids(events: set[str]) -> None:
    st.session_state[_EVENT_STATE_KEY] = sorted(events)


def get_tasks() -> list[TodoTask]:
    """Return the current todo tasks stored in session state."""

    return _ensure_tasks()


def apply_inbox_update(text: str, *, event_id: str | None = None, use_ai: bool = True) -> ProgressInboxResult:
    """Apply an update text to matching tasks and persist the result."""

    tasks = _ensure_tasks()
    processed_events = _get_processed_event_ids()
    if event_id and event_id in processed_events:
        return ProgressInboxResult(
            results=[],
            used_ai=False,
            warning=(
                "Ereignis bereits verarbeitet – Duplikat wird übersprungen. / "
                "Event already processed; skipping duplicate."
            ),
            event_id=event_id,
        )

    warning: str | None = None
    used_ai = False
    plan: ProgressUpdatePlan | None = None
    now = datetime.now(timezone.utc)

    if use_ai:
        if not is_llm_enabled():
            warning = "KI-Abgleich nicht verfügbar (API-Schlüssel fehlt). / AI matching unavailable (missing API key)."
        else:
            try:
                plan = plan_progress_updates(text, tasks)
                used_ai = plan is not None
            except ProgressPlannerError as exc:
                warning = exc.user_message

    results: list[ProgressUpdateResult] = []
    if plan and plan.matches:
        results = apply_plan_matches(text, tasks, plan.matches, now=now, event_id=event_id)

    if not results:
        fallback_result = apply_progress_update(text, tasks, now=now)
        results = [fallback_result]

    if event_id and any(result.updated for result in results):
        processed_events.add(event_id)
        _store_processed_event_ids(processed_events)

    st.session_state[_TASK_STATE_KEY] = [_serialise_task(task) for task in tasks]
    return ProgressInboxResult(results=results, used_ai=used_ai, warning=warning, event_id=event_id)
