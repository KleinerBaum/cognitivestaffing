"""Helpers for invoking the OpenAI Responses API with structured outputs."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from copy import deepcopy
from typing import Any, Mapping, Sequence

from openai import OpenAIError

from config import ModelTask
from openai_utils.api import (
    SchemaFormatBundle,
    _inject_verbosity_hint,
    _resolve_verbosity,
    build_schema_format_bundle,
    LLMResponseFormatError,
    call_chat_api,
)
from llm.response_schemas import INTERVIEW_GUIDE_SCHEMA_NAME, validate_response_schema
from utils.json_repair import JsonRepairStatus, parse_json_with_repair

logger = logging.getLogger("cognitive_needs.llm.responses")


@dataclass(slots=True)
class ResponsesCallResult:
    """Structured return value for :func:`call_responses`."""

    content: str
    usage: dict[str, int]
    response_id: str | None
    raw_response: Any
    used_chat_fallback: bool = False


class ResponsesSchemaError(ValueError):
    """Raised when a Responses payload lacks a JSON schema."""


def build_json_schema_format(
    *,
    name: str,
    schema: Mapping[str, Any] | None,
    strict: bool | None = None,
) -> dict[str, Any]:
    """Return a ``text.format`` payload for JSON schema outputs."""

    if not isinstance(name, str) or not name.strip():
        raise ValueError("A non-empty schema name is required for response_format.")
    if schema is None:
        raise ResponsesSchemaError("Responses schema payload cannot be None. [RESPONSES_PAYLOAD_GUARD]")
    if not isinstance(schema, Mapping):
        raise TypeError("Schema must be a mapping when building response_format.")

    from core.schema import _prune_unsupported_formats
    from core.schema_guard import guard_no_additional_properties

    # Interview guide responses expect a list of entries with ``question``,
    # ``answer``, and ``label`` keys (plus optional notes). Keeping that shape
    # documented here helps avoid regressions like the past missing-``label``
    # error and keeps the schema requirements visible where the Responses
    # payload is assembled.
    schema_payload = guard_no_additional_properties(_prune_unsupported_formats(deepcopy(dict(schema))))
    schema_payload = validate_response_schema(name.strip(), schema_payload)

    if name.strip() == INTERVIEW_GUIDE_SCHEMA_NAME:
        focus_definitions = schema_payload.get("$defs")
        focus_schema = None
        if isinstance(focus_definitions, Mapping):
            focus_schema = focus_definitions.get("InterviewGuideFocusArea")
        if isinstance(focus_schema, Mapping):
            required_fields = list(focus_schema.get("required") or [])
            for field in ("label", "items"):
                if field not in required_fields:
                    required_fields.append(field)
            focus_schema["required"] = required_fields
            focus_definitions["InterviewGuideFocusArea"] = focus_schema

    schema_config: dict[str, Any] = {
        "name": name.strip(),
        "schema": deepcopy(dict(schema_payload)),
    }
    if strict is not None:
        schema_config["strict"] = bool(strict)

    bundle = build_schema_format_bundle(schema_config)
    return deepcopy(bundle.responses_format)


def _prepare_messages(messages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return ``messages`` as a list of plain dictionaries."""

    prepared: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, Mapping):
            raise TypeError("Messages must be mappings when calling the Responses API.")
        prepared.append({str(key): value for key, value in message.items()})
    return prepared


def _build_schema_bundle_from_format(response_format: Mapping[str, Any]) -> SchemaFormatBundle:
    """Normalise a ``response_format`` payload for chat and Responses calls."""

    if not isinstance(response_format, Mapping):
        raise TypeError("response_format must be a mapping payload.")

    json_schema_payload = response_format.get("json_schema")
    if json_schema_payload is not None and not isinstance(json_schema_payload, Mapping):
        raise TypeError("response_format['json_schema'] must be a mapping payload.")

    schema_payload = None
    schema_name: str | None = None
    strict_value: Any | None = None

    if isinstance(json_schema_payload, Mapping):
        schema_payload = json_schema_payload.get("schema")
        schema_name_candidate = json_schema_payload.get("name")
        schema_name = str(schema_name_candidate).strip() if schema_name_candidate is not None else None
        if "strict" in json_schema_payload:
            strict_value = json_schema_payload.get("strict")

    if schema_payload is None and "schema" in response_format:
        schema_payload = response_format.get("schema")

    if schema_name is None and "name" in response_format:
        schema_name_candidate = response_format.get("name")
        schema_name = str(schema_name_candidate or "").strip()

    if schema_payload is None:
        raise ResponsesSchemaError("Responses payload requires a schema. [RESPONSES_PAYLOAD_GUARD]")
    if not isinstance(schema_payload, Mapping):
        raise TypeError("Responses payload requires a mapping schema. [RESPONSES_PAYLOAD_GUARD]")

    if not schema_name:
        raise ResponsesSchemaError("Responses payload requires a schema name. [RESPONSES_PAYLOAD_GUARD]")

    if strict_value is None and "strict" in response_format:
        strict_value = response_format.get("strict")

    schema_config: dict[str, Any] = {"name": schema_name, "schema": schema_payload}
    if strict_value is not None:
        schema_config["strict"] = strict_value

    return build_schema_format_bundle(schema_config)


def call_responses(
    messages: Sequence[Mapping[str, Any]],
    *,
    model: str,
    response_format: Mapping[str, Any],
    temperature: float | None = None,
    max_completion_tokens: int | None = None,
    reasoning_effort: str | None = None,
    verbosity: str | None = None,
    retries: int = 2,
    task: ModelTask | str | None = None,
) -> ResponsesCallResult:
    """Execute a structured chat call with schema enforcement."""

    _ = retries  # retained for backwards compatibility with callers

    schema_bundle = _build_schema_bundle_from_format(response_format)

    prepared_messages = _prepare_messages(_inject_verbosity_hint(messages, _resolve_verbosity(verbosity)))

    json_schema_payload: dict[str, Any] = {
        "name": schema_bundle.name,
        "schema": deepcopy(schema_bundle.schema),
    }
    if schema_bundle.strict is not None:
        json_schema_payload["strict"] = schema_bundle.strict

    chat_result = call_chat_api(
        prepared_messages,
        model=model,
        temperature=temperature,
        max_completion_tokens=max_completion_tokens,
        json_schema=json_schema_payload,
        reasoning_effort=reasoning_effort,
        verbosity=verbosity,
        task=task,
        include_raw_response=True,
        use_response_format=True,
    )

    content = (chat_result.content or "").strip()

    return ResponsesCallResult(
        content=content,
        usage=dict(chat_result.usage or {}),
        response_id=chat_result.response_id,
        raw_response=chat_result.raw_response,
        used_chat_fallback=False,
    )


def call_responses_safe(
    messages: Sequence[Mapping[str, Any]],
    *,
    model: str,
    response_format: Mapping[str, Any],
    logger_instance: logging.Logger | None = None,
    context: str = "call",
    allow_empty: bool = False,
    verbosity: str | None = None,
    **kwargs: Any,
) -> ResponsesCallResult | None:
    """Return a Responses result or ``None`` when the call should fall back.

    The helper wraps :func:`call_responses` with defensive error handling so
    callers can centralise fallback behaviour. All keyword arguments other than
    ``logger_instance``, ``context`` and ``allow_empty`` are forwarded to
    :func:`call_responses`.
    """

    active_logger = logger_instance or logger

    try:
        result = call_responses(
            messages,
            model=model,
            response_format=response_format,
            verbosity=verbosity,
            **kwargs,
        )
    except ResponsesSchemaError as exc:
        active_logger.error(
            "Schema payload guard blocked %s call: %s",
            context,
            exc,
        )
        return None
    except (OpenAIError, LLMResponseFormatError) as exc:
        active_logger.error(
            "Structured chat call for %s failed: %s",
            context,
            exc,
        )
        return None
    except Exception as exc:  # pragma: no cover - defensive
        active_logger.warning(
            "Unexpected error during structured %s call",
            context,
            exc_info=exc,
        )
        return None

    content = (result.content or "").strip()
    expects_json = False
    if isinstance(response_format, Mapping):
        format_type = str(response_format.get("type") or "").lower()
        expects_json = format_type == "json_schema" or bool(response_format.get("json_schema"))
    if expects_json and content:
        repair_attempt = parse_json_with_repair(content)
        if repair_attempt.payload is not None:
            repaired_content = json.dumps(repair_attempt.payload, ensure_ascii=False)
            result.content = repaired_content.strip()
            if repair_attempt.status is JsonRepairStatus.REPAIRED:
                active_logger.info(
                    "Structured %s JSON was repaired before returning result.",
                    context,
                )
            return result

        active_logger.error("Structured %s call returned invalid JSON.", context)
        return None
    if not allow_empty and not content:
        active_logger.info("Structured %s call returned empty content", context)
        return None

    result.content = content
    return result


__all__ = [
    "ResponsesCallResult",
    "build_json_schema_format",
    "call_responses",
    "call_responses_safe",
]
