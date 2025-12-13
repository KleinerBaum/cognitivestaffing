from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
import re
from typing import Iterable, Sequence

from models.progress_updates import ProgressAction, ProgressUpdateMatch


_PROGRESS_NUMBER_PATTERN = re.compile(
    r"(?P<sign>[+-])?\s*(?P<num>\d+)\s*(?:x|times|bewerbungen|applications)?", re.IGNORECASE
)


def _normalize_text(value: str) -> str:
    """Lowercase and remove punctuation for stable comparisons."""

    cleaned = re.sub(r"[^\w\s]", " ", value.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _tokenize(value: str) -> set[str]:
    """Return a set of normalized tokens from the given text."""

    normalized = _normalize_text(value)
    return {token for token in normalized.split(" ") if token}


@dataclass(slots=True)
class TodoNote:
    """Represents a single note attached to a task."""

    text: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(slots=True)
class TodoTask:
    """Represents a task with optional numeric progress."""

    task_id: str
    title: str
    description: str
    progress_current: int = 0
    progress_target: int | None = None
    notes: list[TodoNote] = field(default_factory=list)

    def add_note(self, text: str, *, created_at: datetime | None = None) -> None:
        timestamp = created_at or datetime.now(timezone.utc)
        self.notes.append(TodoNote(text=text, created_at=timestamp))


@dataclass(slots=True)
class ProgressUpdateResult:
    """Outcome of applying a progress update to a task list."""

    updated: bool
    matched_task: TodoTask | None
    score: float
    progress_delta: int | None = None
    message: str = ""
    action: ProgressAction | None = None
    note_text: str | None = None
    event_id: str | None = None
    rationale: str | None = None


def parse_progress_delta(text: str) -> int | None:
    """Extract a numeric delta from the input text if present.

    Supports simple patterns such as ``"+2"``, ``"2 Bewerbungen"``, or ``"2x"``.
    Returns ``None`` when no usable number is found.
    """

    match = _PROGRESS_NUMBER_PATTERN.search(text)
    if not match:
        return None
    raw = int(match.group("num"))
    sign = match.group("sign") or "+"
    return raw if sign == "+" else -raw


def _apply_note(
    task: TodoTask,
    note_text: str,
    *,
    score: float,
    now: datetime,
    action: ProgressAction,
    event_id: str | None = None,
    rationale: str | None = None,
) -> ProgressUpdateResult:
    cleaned_note = note_text.strip() or note_text
    task.add_note(cleaned_note, created_at=now)
    return ProgressUpdateResult(
        updated=True,
        matched_task=task,
        score=score,
        message="Note added to task.",
        action=action,
        note_text=cleaned_note,
        event_id=event_id,
        rationale=rationale,
    )


def _apply_progress_delta(
    task: TodoTask,
    delta: int,
    *,
    score: float,
    now: datetime,
    event_id: str | None = None,
    rationale: str | None = None,
) -> ProgressUpdateResult:
    if task.progress_target is None:
        return _apply_note(
            task,
            f"Progress update (+{delta})",
            score=score,
            now=now,
            action="add_note",
            event_id=event_id,
            rationale=rationale,
        )

    updated_progress = task.progress_current + delta
    capped_progress = min(max(updated_progress, 0), task.progress_target)
    task.progress_current = capped_progress

    return ProgressUpdateResult(
        updated=True,
        matched_task=task,
        score=score,
        progress_delta=delta,
        message=(f"Progress updated ({task.progress_current}/{task.progress_target})."),
        action="increment_progress",
        event_id=event_id,
        rationale=rationale,
    )


def _mark_task_done(
    task: TodoTask,
    *,
    score: float,
    now: datetime,
    event_id: str | None = None,
    rationale: str | None = None,
) -> ProgressUpdateResult:
    if task.progress_target is None:
        return _apply_note(
            task,
            "Marked as done",
            score=score,
            now=now,
            action="mark_done",
            event_id=event_id,
            rationale=rationale,
        )

    task.progress_current = task.progress_target
    return ProgressUpdateResult(
        updated=True,
        matched_task=task,
        score=score,
        progress_delta=0,
        message=(f"Marked as done ({task.progress_current}/{task.progress_target})."),
        action="mark_done",
        event_id=event_id,
        rationale=rationale,
    )


def apply_action_to_task(
    task: TodoTask,
    *,
    action: ProgressAction,
    update_text: str,
    amount: float | None,
    note: str | None,
    score: float,
    now: datetime,
    event_id: str | None = None,
    rationale: str | None = None,
) -> ProgressUpdateResult:
    if action == "increment_progress":
        delta = int(round(amount)) if amount is not None else parse_progress_delta(update_text) or 1
        return _apply_progress_delta(
            task,
            delta,
            score=score,
            now=now,
            event_id=event_id,
            rationale=rationale,
        )

    if action == "mark_done":
        return _mark_task_done(
            task,
            score=score,
            now=now,
            event_id=event_id,
            rationale=rationale,
        )

    note_text = note or update_text
    if action == "move_subtask":
        prefix = "[Moved subtask] "
        if not note_text.strip().lower().startswith(prefix.lower()):
            note_text = f"{prefix}{note_text}"
    return _apply_note(
        task,
        note_text,
        score=score,
        now=now,
        action=action,
        event_id=event_id,
        rationale=rationale,
    )


def apply_plan_matches(
    update_text: str,
    tasks: Sequence[TodoTask],
    matches: Sequence[ProgressUpdateMatch],
    *,
    now: datetime | None = None,
    event_id: str | None = None,
) -> list[ProgressUpdateResult]:
    """Apply an LLM-produced match plan to the provided tasks."""

    timestamp = now or datetime.now(timezone.utc)
    results: list[ProgressUpdateResult] = []
    task_map = {task.task_id: task for task in tasks}
    for match in matches[:3]:
        task = task_map.get(match.todo_id)
        if task is None:
            continue
        results.append(
            apply_action_to_task(
                task,
                action=match.action,
                update_text=update_text,
                amount=match.amount,
                note=match.note,
                score=match.confidence,
                now=timestamp,
                event_id=event_id,
                rationale=match.rationale_short,
            )
        )
    return results


def _score_task_match(task: TodoTask, update_tokens: set[str]) -> float:
    """Return a similarity score between the update and a task."""

    task_tokens = _tokenize(task.title) | _tokenize(task.description)
    if not task_tokens or not update_tokens:
        return 0.0

    overlap = len(task_tokens & update_tokens) / max(len(update_tokens), 1)
    sequence_ratio = SequenceMatcher(None, " ".join(sorted(update_tokens)), " ".join(sorted(task_tokens))).ratio()
    return (overlap * 0.7) + (sequence_ratio * 0.3)


def match_task(update_text: str, tasks: Sequence[TodoTask], *, threshold: float = 0.35) -> ProgressUpdateResult:
    """Find the best matching task based on token overlap and sequence similarity."""

    update_tokens = _tokenize(update_text)
    best_task: TodoTask | None = None
    best_score = 0.0
    for task in tasks:
        score = _score_task_match(task, update_tokens)
        if score > best_score:
            best_score = score
            best_task = task

    if best_task is None or best_score < threshold:
        return ProgressUpdateResult(
            updated=False,
            matched_task=None,
            score=best_score,
            message="No matching task found.",
        )

    return ProgressUpdateResult(updated=False, matched_task=best_task, score=best_score)


def apply_progress_update(
    update_text: str,
    tasks: Iterable[TodoTask],
    *,
    threshold: float = 0.35,
    now: datetime | None = None,
) -> ProgressUpdateResult:
    """Apply the given update text to the best matching task.

    When the matched task defines a ``progress_target``, ``progress_current`` is
    incremented (default ``+1`` unless a numeric delta is present). For tasks
    without a numeric target, the update text is stored as a timestamped note.
    """

    task_list = list(tasks)
    match_result = match_task(update_text, task_list, threshold=threshold)
    if match_result.matched_task is None:
        return match_result

    target_task = match_result.matched_task
    timestamp = now or datetime.now(timezone.utc)
    if target_task.progress_target is not None:
        delta = parse_progress_delta(update_text) or 1
        return _apply_progress_delta(
            target_task,
            delta,
            score=match_result.score,
            now=timestamp,
        )

    return _apply_note(
        target_task,
        update_text,
        score=match_result.score,
        now=timestamp,
        action="add_note",
    )
