"""Follow-up question generation pipeline."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any

from config import ModelTask, get_active_verbosity, get_model_for
from openai_utils import call_chat_api
from openai_utils.tools import build_file_search_tool
from prompts import prompt_registry
from schemas import FOLLOW_UPS_SCHEMA

__all__ = ["generate_followups"]


logger = logging.getLogger(__name__)


def _parse_followup_response(response: Any) -> dict[str, Any]:
    """Normalise a follow-up response into a mapping with a questions list."""

    default: dict[str, Any] = {"questions": []}

    if response is None:
        return default

    payload: Any = response
    if isinstance(response, Mapping):
        payload = dict(response)
    else:
        content = getattr(response, "content", None)
        if content is not None:
            payload = content

    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except (TypeError, ValueError):
            return default
        if not isinstance(parsed, Mapping):
            return default
        payload = parsed

    if isinstance(payload, Mapping):
        result = dict(payload)
        if not isinstance(result.get("questions"), list):
            result["questions"] = []
        return result

    return default


def generate_followups(
    vacancy_json: dict,
    lang: str,
    vector_store_id: str | None = None,
) -> dict[str, Any]:
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

    try:
        response = call_chat_api(
            messages=[system, user],
            model=get_model_for(ModelTask.FOLLOW_UP_QUESTIONS),
            temperature=0.2,
            tools=tools or None,
            tool_choice=tool_choice,
            json_schema={
                "name": "FollowUpQuestions",
                "schema": FOLLOW_UPS_SCHEMA,
                "strict": False,
            },
            task=ModelTask.FOLLOW_UP_QUESTIONS,
            verbosity=get_active_verbosity(),
        )
        return _parse_followup_response(response)
    except Exception as exc:  # pragma: no cover - defensive guard for UI fallback
        logger.warning("Follow-up generation failed; returning no questions.", exc_info=exc)
        return {"questions": []}
