"""Follow-up question generation pipeline."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any

from config import get_active_verbosity
from config.models import ModelTask, get_model_for
from openai_utils import call_chat_api
from openai_utils.tools import build_file_search_tool
from prompts import prompt_registry

__all__ = ["generate_followups"]


logger = logging.getLogger(__name__)


_FALLBACK_FOLLOWUPS: dict[str, list[dict[str, Any]]] = {
    "en": [
        {
            "field": "company.name",
            "question": "What is the company's official name?",
            "priority": "critical",
            "suggestions": [
                "Use the registered brand name",
                "Confirm the correct spelling",
            ],
        },
        {
            "field": "position.job_title",
            "question": "What is the exact job title for this role?",
            "priority": "normal",
            "suggestions": [
                "Software Engineer (Backend)",
                "Product Manager",
            ],
        },
        {
            "field": "position.location",
            "question": "Where will the role be based?",
            "priority": "optional",
            "suggestions": [
                "Berlin (onsite)",
                "Remote (EU)",
            ],
        },
    ],
    "de": [
        {
            "field": "company.name",
            "question": "Wie lautet der offizielle Firmenname?",
            "priority": "critical",
            "suggestions": [
                "Registrierten Markennamen nutzen",
                "Schreibweise bestätigen",
            ],
        },
        {
            "field": "position.job_title",
            "question": "Wie lautet die genaue Stellenbezeichnung?",
            "priority": "normal",
            "suggestions": [
                "Software Engineer (Backend)",
                "Product Manager",
            ],
        },
        {
            "field": "position.location",
            "question": "Wo ist die Stelle angesiedelt?",
            "priority": "optional",
            "suggestions": [
                "Berlin (vor Ort)",
                "Remote (EU)",
            ],
        },
    ],
}


def _fallback_followups(lang: str) -> dict[str, Any]:
    """Return a minimal set of follow-up questions when the LLM fails."""

    locale = "de" if lang.lower().startswith("de") else "en"
    questions = _FALLBACK_FOLLOWUPS.get(locale, _FALLBACK_FOLLOWUPS["en"])
    return {"questions": list(questions)}


def _normalise_question(item: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return a schema-compliant question entry or ``None`` when invalid."""

    field = str(item.get("field") or "").strip()
    question = str(item.get("question") or "").strip()
    if not field or not question:
        return None

    priority = str(item.get("priority") or "normal").strip() or "normal"
    suggestions_raw = item.get("suggestions")
    suggestions: list[str] = []
    if isinstance(suggestions_raw, list):
        suggestions = [str(s).strip() for s in suggestions_raw if str(s).strip()]
    if not suggestions:
        suggestions = [question]

    result: dict[str, Any] = {
        "field": field,
        "question": question,
        "priority": priority,
        "suggestions": suggestions,
    }

    depends_on_raw = item.get("depends_on")
    if isinstance(depends_on_raw, list):
        depends_on_clean = [str(value).strip() for value in depends_on_raw if str(value).strip()]
        if depends_on_clean:
            result["depends_on"] = depends_on_clean

    rationale = item.get("rationale")
    if isinstance(rationale, str) and rationale.strip():
        result["rationale"] = rationale.strip()

    return result


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
        questions_raw = payload.get("questions")
        if not isinstance(questions_raw, list):
            return default

        questions: list[dict[str, Any]] = []
        for item in questions_raw:
            if isinstance(item, Mapping):
                normalised = _normalise_question(item)
                if normalised:
                    questions.append(normalised)

        return {"questions": questions}

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
            json_schema=None,
            task=ModelTask.FOLLOW_UP_QUESTIONS,
            verbosity=get_active_verbosity(),
            use_response_format=False,
        )
        parsed = _parse_followup_response(response)
        if parsed.get("questions"):
            return parsed
        logger.info("Follow-up generation returned no questions; using fallback prompts.")
        return _fallback_followups(lang)
    except Exception as exc:  # pragma: no cover - defensive guard for UI fallback
        logger.warning("Follow-up generation failed; returning fallback questions.", exc_info=exc)
        return _fallback_followups(lang)
