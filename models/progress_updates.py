from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ProgressAction = Literal["increment_progress", "mark_done", "add_note", "move_subtask"]


class ProgressUpdateMatch(BaseModel):
    """Single match suggestion for a todo item.

    Attributes:
        todo_id: Identifier of the todo/task to update.
        action: The action to apply (increment, mark done, add note, move subtask).
        amount: Optional numeric increment; interpreted as a delta towards the target.
        note: Optional note text to attach to the task.
        confidence: Confidence score (0–1) indicating how confident the model is.
        rationale_short: Optional, single-sentence rationale for the match.
    """

    todo_id: str = Field(..., min_length=1)
    action: ProgressAction
    amount: float | None = None
    note: str | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    rationale_short: str | None = Field(None, max_length=240)


class ProgressUpdatePlan(BaseModel):
    """Structured plan of todo updates returned by the model."""

    matches: list[ProgressUpdateMatch] = Field(default_factory=list, max_length=3)
