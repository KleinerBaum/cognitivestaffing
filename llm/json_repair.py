"""Fallback helpers that use the Responses API to repair profile JSON payloads."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any, Mapping, Sequence

from config import is_llm_enabled
from config.models import ModelTask, get_model_for, mark_model_unavailable
from core.schema_registry import load_need_analysis_schema
from llm.openai_responses import (
    ResponsesCallResult,
    build_json_schema_format,
    call_responses_safe,
)
from llm.profile_normalization import normalize_interview_stages_field
from pydantic import AnyUrl, HttpUrl
from utils.json_repair import JsonRepairResult, parse_json_with_repair

logger = logging.getLogger(__name__)

_SCHEMA_NAME = "need_analysis_profile"
_JSON_REPAIR_MAX_RETRIES = 2


def _coerce_json_serializable(value: Any) -> Any:
    """Return ``value`` converted into a JSON-serializable structure."""

    if isinstance(value, (HttpUrl, AnyUrl)):
        return str(value)
    if isinstance(value, Mapping):
        return {key: _coerce_json_serializable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_coerce_json_serializable(item) for item in value]

    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


@lru_cache(maxsize=1)
def _load_schema() -> Mapping[str, Any] | None:
    """Return the cached NeedAnalysisProfile JSON schema."""

    try:
        return load_need_analysis_schema()
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to load need analysis schema: %s", exc)
    return None


def _format_error_summary(errors: Sequence[Mapping[str, Any]] | None) -> str:
    """Return a bullet list describing validation issues."""

    if not errors:
        return "- (no validation details available)"
    lines: list[str] = []
    for entry in errors:
        loc = entry.get("loc")
        if isinstance(loc, (list, tuple)):
            path = ".".join(str(part) for part in loc if part is not None)
        else:
            path = str(loc or "<root>")
        message = str(entry.get("msg") or entry.get("type") or "invalid value")
        lines.append(f"- {path or '<root>'}: {message}")
    return "\n".join(lines)


def parse_profile_json(raw: str, *, errors: Sequence[Mapping[str, Any]] | None = None) -> JsonRepairResult:
    """Parse ``raw`` and attempt to repair invalid NeedAnalysis JSON."""

    return parse_json_with_repair(raw, errors=errors, repair_func=repair_profile_payload)


def repair_profile_payload(
    payload: Mapping[str, Any], errors: Sequence[Mapping[str, Any]] | None = None
) -> Mapping[str, Any] | None:
    """Return a repaired NeedAnalysisProfile payload using an LLM fallback."""

    if not is_llm_enabled():
        logger.debug("Skipping JSON repair because no OpenAI API key is configured.")
        return None

    schema = _load_schema()
    if not schema:
        return None

    model = get_model_for(ModelTask.JSON_REPAIR)
    response_format = build_json_schema_format(name=_SCHEMA_NAME, schema=schema)

    serializable_payload = _coerce_json_serializable(payload)

    try:
        payload_text = json.dumps(serializable_payload, ensure_ascii=False, indent=2, sort_keys=True)
    except TypeError:
        fallback_payload = _coerce_json_serializable(dict(payload))
        try:
            payload_text = json.dumps(fallback_payload, ensure_ascii=False, indent=2, sort_keys=True)
        except TypeError:
            payload_text = json.dumps(
                fallback_payload,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                default=str,
            )

    error_summary = _format_error_summary(errors)
    system_prompt = (
        "You fix JSON objects for the hiring NeedAnalysisProfile schema. "
        "Return a single JSON object that conforms to the schema, preserves valid "
        "data, and leaves uncertain fields null. Do not include explanations."
    )
    user_prompt = (
        "Source JSON (may be invalid):\n"
        f"{payload_text}\n\n"
        "Validation issues:\n"
        f"{error_summary}\n\n"
        "Respond with corrected JSON only."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    def _invoke_repair(target_model: str) -> ResponsesCallResult | None:
        try:
            return call_responses_safe(
                messages,
                model=target_model,
                response_format=response_format,
                temperature=0.0,
                max_completion_tokens=800,
                task=ModelTask.JSON_REPAIR,
                logger_instance=logger,
                context="json repair",
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("JSON repair call failed: %s", exc)
            return None

    response: ResponsesCallResult | None = None
    attempted_models: list[str] = []
    target_model = model
    for _ in range(_JSON_REPAIR_MAX_RETRIES):
        attempted_models.append(target_model)
        response = _invoke_repair(target_model)
        if response is not None and (response.content or "").strip():
            break
        mark_model_unavailable(target_model)
        alternate_model = get_model_for(ModelTask.JSON_REPAIR)
        if alternate_model == target_model:
            break
        logger.warning("Retrying JSON repair with alternate model: %s", alternate_model)
        target_model = alternate_model

    if response is None or not (response.content or "").strip():
        logger.error(
            "All API attempts failed for JSON repair task after %d tries (%s).",
            len(attempted_models),
            ", ".join(attempted_models),
        )
        return None

    if response.used_chat_fallback:
        logger.info("JSON repair succeeded via classic chat fallback")

    if not response.content:
        logger.debug("JSON repair returned empty content.")
        return None

    try:
        repaired = json.loads(response.content)
    except json.JSONDecodeError as exc:
        logger.debug("JSON repair response was not valid JSON: %s", exc)
        return None

    if not isinstance(repaired, Mapping):
        logger.debug("JSON repair response was not an object: %s", type(repaired))
        return None

    result = dict(repaired)
    normalize_interview_stages_field(result)
    return result


def repair_json_payload(
    raw: str,
    *,
    schema_name: str,
    schema: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    """Return a repaired JSON payload using the provided schema."""

    if not is_llm_enabled():
        logger.debug("Skipping JSON repair because no OpenAI API key is configured.")
        return None

    response_format = build_json_schema_format(name=schema_name, schema=schema)
    system_prompt = (
        "You repair invalid JSON outputs to match the provided schema. "
        "Return JSON only with no markdown, code fences, or prose."
    )
    user_prompt = f"Invalid JSON (may include extra text):\n{raw}\n\nReturn corrected JSON only."
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response: ResponsesCallResult | None = None
    target_model = get_model_for(ModelTask.JSON_REPAIR)
    for _ in range(_JSON_REPAIR_MAX_RETRIES):
        response = call_responses_safe(
            messages,
            model=target_model,
            response_format=response_format,
            temperature=0.0,
            max_completion_tokens=600,
            task=ModelTask.JSON_REPAIR,
            logger_instance=logger,
            context=f"{schema_name} json repair",
        )
        if response is not None and response.content:
            break
        mark_model_unavailable(target_model)
        alternate_model = get_model_for(ModelTask.JSON_REPAIR)
        if alternate_model == target_model:
            break
        target_model = alternate_model

    if response is None or not response.content:
        return None

    try:
        repaired = json.loads(response.content)
    except json.JSONDecodeError:
        return None

    if isinstance(repaired, Mapping):
        return dict(repaired)
    return None


def retry_profile_payload(
    payload: Mapping[str, Any],
    *,
    source_text: str,
    focus_fields: Sequence[str],
    reason: str,
) -> Mapping[str, Any] | None:
    """Request a focused extraction retry before generic JSON repair.

    This helper is used when validation succeeds syntactically but semantically
    critical fields are still empty although the source text contains cues.
    """

    if not is_llm_enabled():
        return None

    schema = _load_schema()
    if not schema:
        return None

    model = get_model_for(ModelTask.EXTRACTION)
    response_format = build_json_schema_format(name=_SCHEMA_NAME, schema=schema)
    focused_fields = ", ".join(field.strip() for field in focus_fields if field.strip())
    payload_text = json.dumps(_coerce_json_serializable(payload), ensure_ascii=False, indent=2, sort_keys=True)
    system_prompt = (
        "You are retrying structured profile extraction. "
        "Return a single JSON object conforming to the schema. "
        "Prioritise completeness for the requested focus fields when evidence exists. "
        "If evidence is absent, keep fields as empty lists."
    )
    user_prompt = (
        f"Retry reason: {reason}\n"
        f"Focus fields: {focused_fields or '<none>'}\n\n"
        "Current extracted JSON:\n"
        f"{payload_text}\n\n"
        "Source text:\n"
        f"{source_text.strip()}\n\n"
        "Return corrected JSON only."
    )

    response = call_responses_safe(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=model,
        response_format=response_format,
        temperature=0.0,
        max_completion_tokens=1000,
        task=ModelTask.EXTRACTION,
        logger_instance=logger,
        context="extraction retry",
    )
    if response is None or not response.content:
        return None
    try:
        candidate = json.loads(response.content)
    except json.JSONDecodeError:
        return None
    if isinstance(candidate, Mapping):
        result = dict(candidate)
        normalize_interview_stages_field(result)
        return result
    return None


__all__ = [
    "parse_profile_json",
    "repair_profile_payload",
    "repair_json_payload",
    "retry_profile_payload",
]
