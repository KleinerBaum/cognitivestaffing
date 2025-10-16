"""Follow-up question generation pipeline."""

from __future__ import annotations

from typing import Any

from config import ModelTask, get_active_verbosity, get_model_for
from openai_utils import call_chat_api
from openai_utils.tools import build_file_search_tool
from prompts import prompt_registry
from schemas import FOLLOW_UPS_SCHEMA

__all__ = ["generate_followups"]


def generate_followups(
    vacancy_json: dict,
    lang: str,
    vector_store_id: str | None = None,
) -> Any:
    """Generate prioritised follow-up questions for a vacancy profile."""

    system = {
        "role": "system",
        "content": prompt_registry.get("pipelines.followups.system"),
    }
    user = {
        "role": "user",
        "content": f"Sprache: {lang}\nAktuelles Profil:\n{vacancy_json}",
    }
    tools: list[dict[str, Any]] = []
    tool_choice: str | None = None
    if vector_store_id:
        tools.append(build_file_search_tool(vector_store_id))
        tool_choice = "auto"

    return call_chat_api(
        messages=[system, user],
        model=get_model_for(ModelTask.FOLLOW_UP_QUESTIONS),
        temperature=0.2,
        tools=tools or None,
        tool_choice=tool_choice,
        json_schema={"name": "FollowUpQuestions", "schema": FOLLOW_UPS_SCHEMA},
        task=ModelTask.FOLLOW_UP_QUESTIONS,
        verbosity=get_active_verbosity(),
    )
