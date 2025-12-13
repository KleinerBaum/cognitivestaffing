from __future__ import annotations

import logging
from typing import Sequence

from openai import OpenAI, OpenAIError

from config import (
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_REQUEST_TIMEOUT,
    ModelTask,
    get_model_for,
    is_llm_enabled,
)
from core.progress_updates import TodoTask
from models.progress_updates import ProgressUpdatePlan

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = "\n".join(
    [
        "You map natural language progress inbox updates to existing todo items.",
        "Return a JSON plan with up to 3 matches sorted by confidence (highest first).",
        "Allowed actions: increment_progress (use amount as delta), mark_done, add_note, move_subtask.",
        "Prefer mark_done when the update clearly signals completion.",
        "Use add_note when the update is purely informational or when no numeric target exists.",
        "Skip todos you are not confident about instead of guessing.",
        "The rationale_short must be at most one sentence.",
    ]
)


class ProgressPlannerError(RuntimeError):
    """Raised when the AI planner fails and a fallback is required."""

    def __init__(self, message: str, *, user_message: str | None = None):
        super().__init__(message)
        self.user_message = user_message or message


def _build_openai_client() -> OpenAI:
    return OpenAI(
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        timeout=OPENAI_REQUEST_TIMEOUT,
    )


def _compact_task_list(tasks: Sequence[TodoTask]) -> str:
    """Return a compact, newline-separated list of tasks for prompting."""

    entries: list[str] = []
    for task in tasks:
        target = task.progress_target
        rule_summary = (
            f"Target {task.progress_target} (current {task.progress_current}); increment counts and auto-complete at target."
            if target is not None
            else "Note-only task; capture text updates instead of numeric progress."
        )
        entries.append(
            " | ".join(
                [
                    f"id: {task.task_id}",
                    f"title: {task.title}",
                    "category: general",
                    "due: n/a",
                    f"rule: {rule_summary}",
                    f"description: {task.description}",
                ]
            )
        )
    return "\n".join(entries)


def plan_progress_updates(update_text: str, tasks: Sequence[TodoTask]) -> ProgressUpdatePlan | None:
    """Use OpenAI to align an inbox update with existing todos.

    Returns ``None`` when LLM usage is disabled or no API key is configured.
    """

    if not update_text.strip():
        return None
    if not is_llm_enabled() or not OPENAI_API_KEY:
        return None

    model = get_model_for(ModelTask.PROGRESS_INBOX)
    client = _build_openai_client()
    try:
        response = client.responses.parse(  # type: ignore[call-arg]
            model=model,
            input=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": "\n".join(
                        [
                            "User progress update:",
                            update_text.strip(),
                            "",
                            "Current todos (id, title, category, due, progress rule):",
                            _compact_task_list(tasks),
                            "",
                            "Return at most 3 matches sorted by confidence.",
                        ]
                    ),
                },
            ],
            response_model=ProgressUpdatePlan,
            temperature=0.2,
            max_output_tokens=600,
        )
    except OpenAIError as exc:  # pragma: no cover - exercised via mocked path
        logger.warning("Progress inbox matching failed: %s", exc)
        raise ProgressPlannerError(
            "OpenAI call failed",
            user_message=(
                "KI-Matching fehlgeschlagen – deterministische Zuordnung aktiv. / "
                "AI matching failed – falling back to deterministic matching."
            ),
        ) from exc
    except Exception as exc:  # pragma: no cover - defensive catch-all
        logger.exception("Unexpected planner error")
        raise ProgressPlannerError(
            "Unexpected error during progress planning",
            user_message=(
                "Unerwarteter Fehler beim KI-Matching – deterministische Zuordnung aktiv. / "
                "Unexpected error during AI matching – deterministic path active."
            ),
        ) from exc

    return response.output_parsed
