"""Canonical follow-up generation service."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from jsonschema import ValidationError
from jsonschema.validators import Draft202012Validator

import config.models as model_settings
from config import get_active_verbosity
from prompts import prompt_registry
from wizard._openai_bridge import get_build_file_search_tool, get_call_chat_api

logger = logging.getLogger(__name__)


class LLMCallable(Protocol):
    """Callable signature for follow-up generation LLM calls."""

    def __call__(self, messages: Sequence[Mapping[str, Any]], /, **kwargs: Any) -> Any:
        """Invoke the LLM with a messages payload."""


class ToolBuilder(Protocol):
    """Callable signature for optional file search tool builders."""

    def __call__(self, vector_store_ids: Sequence[str] | str, /, **kwargs: Any) -> dict[str, Any]:
        """Build a tool payload for vector store retrieval."""


@dataclass(frozen=True)
class FollowupModelConfig:
    """Model selection and generation defaults for follow-up questions."""

    fast_model: str = model_settings.GPT4O_MINI
    precise_model: str = model_settings.O3_MINI
    default_model: str | None = None
    model_override: str | None = None
    reasoning_effort: str | None = None
    temperature: float = 0.2
    max_completion_tokens: int = 800


FOLLOWUP_JSON_SCHEMA: dict[str, Any] = {
    "name": "followup_questions",
    "schema": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "field": {"type": "string"},
                        "question": {"type": "string"},
                        "priority": {"type": "string"},
                        "suggestions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                        },
                    },
                    "required": [
                        "field",
                        "question",
                        "priority",
                        "suggestions",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["questions"],
        "additionalProperties": False,
    },
}


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


def _normalize_locale(locale: str) -> str:
    lang = (locale or "en").strip().lower()
    return "de" if lang.startswith("de") else "en"


def _fallback_followups(
    locale: str,
    *,
    reason: str | None = None,
    role_context: str | None = None,
) -> dict[str, Any]:
    """Return a minimal set of follow-up questions when the LLM fails."""

    lang = _normalize_locale(locale)
    questions = list(_FALLBACK_FOLLOWUPS.get(lang, _FALLBACK_FOLLOWUPS["en"]))
    if role_context:
        role_question = {
            "field": "position.context",
            "question": (
                f"Anything else we should know about the role context: {role_context}?"
                if lang == "en"
                else f"Gibt es noch Hinweise zum Rollen-Kontext: {role_context}?"
            ),
            "priority": "optional",
            "suggestions": [role_context],
        }
        questions.append(role_question)
    payload: dict[str, Any] = {"questions": questions, "source": "fallback"}
    if reason:
        payload["fallback_reason"] = reason
    return payload


def _normalize_question(item: Mapping[str, Any]) -> dict[str, Any] | None:
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


_PII_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.IGNORECASE)
_PII_PHONE_RE = re.compile(r"\+?\d[\d\s().-]{6,}\d")
_PII_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def _sanitize_payload_snippet(payload: Any, *, max_length: int = 320) -> str:
    try:
        raw = json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError):
        raw = str(payload)
    redacted = _PII_EMAIL_RE.sub("[redacted-email]", raw)
    redacted = _PII_PHONE_RE.sub("[redacted-phone]", redacted)
    redacted = _PII_URL_RE.sub("[redacted-url]", redacted)
    snippet = redacted.replace("\n", " ").strip()
    if len(snippet) > max_length:
        snippet = f"{snippet[:max_length]}…"
    return snippet


def _parse_followup_response(response: Any) -> dict[str, Any]:
    """Normalise a follow-up response into a mapping with a questions list."""

    default: dict[str, Any] = {"questions": []}
    schema_name = str(FOLLOWUP_JSON_SCHEMA.get("name") or "followup")

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
            logger.warning(
                "Follow-up response failed JSON parsing for schema '%s' (snippet=%s).",
                schema_name,
                _sanitize_payload_snippet(payload),
            )
            return {**default, "fallback_reason": "schema_invalid"}
        if not isinstance(parsed, Mapping):
            logger.warning(
                "Follow-up response JSON was not an object for schema '%s' (snippet=%s).",
                schema_name,
                _sanitize_payload_snippet(parsed),
            )
            return {**default, "fallback_reason": "schema_invalid"}
        payload = parsed

    if isinstance(payload, Mapping):
        try:
            Draft202012Validator(FOLLOWUP_JSON_SCHEMA["schema"]).validate(payload)
        except ValidationError:
            logger.warning(
                "Follow-up response failed schema validation '%s' (snippet=%s).",
                schema_name,
                _sanitize_payload_snippet(payload),
            )
            return {**default, "fallback_reason": "schema_invalid"}
        questions_raw = payload.get("questions")
        if not isinstance(questions_raw, list):
            logger.warning(
                "Follow-up response missing questions list for schema '%s' (snippet=%s).",
                schema_name,
                _sanitize_payload_snippet(payload),
            )
            return {**default, "fallback_reason": "schema_invalid"}

        questions: list[dict[str, Any]] = []
        for item in questions_raw:
            if isinstance(item, Mapping):
                normalised = _normalize_question(item)
                if normalised:
                    questions.append(normalised)

        return {"questions": questions}

    logger.warning(
        "Follow-up response was not a JSON object for schema '%s' (snippet=%s).",
        schema_name,
        _sanitize_payload_snippet(payload),
    )
    return {**default, "fallback_reason": "schema_invalid"}


def _resolve_model(mode: str, cfg: FollowupModelConfig | None) -> str:
    mode_value = (mode or "").strip().lower()
    if cfg and cfg.model_override:
        return cfg.model_override
    if mode_value == "precise":
        return cfg.precise_model if cfg else model_settings.O3_MINI
    if mode_value == "fast":
        return cfg.fast_model if cfg else model_settings.GPT4O_MINI
    if cfg and cfg.default_model:
        return cfg.default_model
    return model_settings.get_model_for(model_settings.ModelTask.FOLLOW_UP_QUESTIONS)


def generate_followups(
    profile: Mapping[str, Any],
    *,
    mode: str = "fast",
    locale: str = "en",
    model_config: FollowupModelConfig | None = None,
    vector_store_id: str | None = None,
    call_llm: LLMCallable | None = None,
    build_file_search_tool: ToolBuilder | None = None,
    previous_response_id: str | None = None,
    role_context: str | None = None,
) -> dict[str, Any]:
    """Generate prioritised follow-up questions for a vacancy profile."""

    call_llm = call_llm or get_call_chat_api()
    build_file_search_tool = build_file_search_tool or get_build_file_search_tool()

    if call_llm is None:
        return _fallback_followups(locale, reason="llm_unavailable", role_context=role_context)

    lang = _normalize_locale(locale)
    system_prompt = prompt_registry.get("question_logic.followups.system", locale=lang)
    strict_system_prompt = (
        f"{system_prompt}\n\n"
        + (
            "Gib ausschließlich valides JSON gemäß dem Schema zurück. Keine Erklärungen."
            if lang == "de"
            else "Return valid JSON only that matches the schema. No explanations."
        )
    )
    user_payload: dict[str, Any] = {"profile": profile}
    if role_context:
        user_payload["role_context"] = role_context

    tools: list[dict[str, Any]] = []
    tool_choice: str | None = None
    if vector_store_id and build_file_search_tool is not None:
        tools.append(build_file_search_tool(vector_store_id))
        tool_choice = "auto"

    config_override = model_config or FollowupModelConfig()
    model = _resolve_model(mode, config_override)

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ]
        response = call_llm(
            messages,
            model=model,
            temperature=config_override.temperature,
            json_schema=FOLLOWUP_JSON_SCHEMA,
            tools=tools or None,
            tool_choice=tool_choice,
            max_completion_tokens=config_override.max_completion_tokens,
            reasoning_effort=config_override.reasoning_effort,
            task=model_settings.ModelTask.FOLLOW_UP_QUESTIONS,
            previous_response_id=previous_response_id,
            verbosity=get_active_verbosity(),
        )
        parsed = _parse_followup_response(response)
        response_id = getattr(response, "response_id", None)
        if response_id:
            parsed["response_id"] = response_id
        if parsed.get("fallback_reason") == "schema_invalid":
            logger.info("Follow-up response schema invalid; retrying once with strict prompt.")
            time.sleep(0.5)
            response = call_llm(
                [
                    {"role": "system", "content": strict_system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
                model=model,
                temperature=config_override.temperature,
                json_schema=FOLLOWUP_JSON_SCHEMA,
                tools=tools or None,
                tool_choice=tool_choice,
                max_completion_tokens=config_override.max_completion_tokens,
                reasoning_effort=config_override.reasoning_effort,
                task=model_settings.ModelTask.FOLLOW_UP_QUESTIONS,
                previous_response_id=previous_response_id,
                verbosity=get_active_verbosity(),
            )
            parsed = _parse_followup_response(response)
            response_id = getattr(response, "response_id", None)
            if response_id:
                parsed["response_id"] = response_id
        if parsed.get("questions"):
            parsed.setdefault("source", "llm")
            return parsed
        fallback_reason = parsed.get("fallback_reason") or "empty_result"
        logger.info("Follow-up generation returned no questions; using fallback prompts.")
        return _fallback_followups(locale, reason=fallback_reason, role_context=role_context)
    except Exception as exc:  # pragma: no cover - defensive guard for UI fallback
        logger.warning("Follow-up generation failed; returning fallback questions.", exc_info=exc)
        return _fallback_followups(locale, reason="llm_error", role_context=role_context)


__all__ = [
    "FOLLOWUP_JSON_SCHEMA",
    "FollowupModelConfig",
    "generate_followups",
]
