"""Helpers for invoking the OpenAI Responses API with structured outputs."""

from __future__ import annotations

import logging
import json
import re
from dataclasses import dataclass
from copy import deepcopy
from typing import Any, Mapping, Sequence

from opentelemetry import trace
from openai import BadRequestError, OpenAIError

import config as app_config
from config import OPENAI_REQUEST_TIMEOUT, ModelTask, temporarily_force_classic_api
from openai_utils.api import (
    _coerce_token_count,
    _extract_output_text,
    _extract_response_id,
    _extract_usage_block,
    _inject_verbosity_hint,
    _is_temperature_unsupported_error,
    _mark_model_without_temperature,
    _normalise_usage,
    _resolve_verbosity,
    _to_mapping,
    _update_usage_counters,
    build_schema_format_bundle,
    call_chat_api,
    get_client,
    is_unrecoverable_schema_error,
    model_supports_reasoning,
    model_supports_temperature,
    SchemaFormatBundle,
)
from llm.response_schemas import INTERVIEW_GUIDE_SCHEMA_NAME, validate_response_schema
from utils.retry import retry_with_backoff

logger = logging.getLogger("cognitive_needs.llm.responses")
tracer = trace.get_tracer(__name__)


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


def _build_function_tool_from_schema(schema_bundle: SchemaFormatBundle) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a chat ``function`` payload mirroring the JSON schema."""

    configured_name = (app_config.SCHEMA_FUNCTION_NAME or "").strip()
    base_name = configured_name or f"extract_{schema_bundle.name}"
    safe_name = re.sub(r"[^\w.-]", "_", base_name) or f"extract_{schema_bundle.name}"
    description = (app_config.SCHEMA_FUNCTION_DESCRIPTION or "").strip()

    return (
        {
            "name": safe_name,
            "description": description
            or "Extract the structured profile payload / Extrahiere die strukturierte Profilantwort.",
            "parameters": deepcopy(schema_bundle.schema),
        },
        {"name": safe_name},
    )


def _run_chat_fallback(
    messages: Sequence[Mapping[str, Any]],
    *,
    model: str,
    response_format: Mapping[str, Any],
    logger_instance: logging.Logger,
    context: str,
    allow_empty: bool,
    temperature: float | None,
    max_completion_tokens: int | None,
    reasoning_effort: str | None,
    verbosity: str | None,
    task: ModelTask | str | None,
    reason: str,
    exc: Exception | None,
) -> ResponsesCallResult | None:
    """Fallback to the classic chat API and return a :class:`ResponsesCallResult`."""

    def _call_function_schema_fallback(schema_bundle: SchemaFormatBundle) -> ResponsesCallResult | None:
        def _extract_function_payload(response: Any) -> str | None:
            for choice in getattr(response, "choices", []) or []:
                choice_map = _to_mapping(choice) or {}
                message = choice_map.get("message")
                message_map = _to_mapping(message) or {}
                tool_calls = message_map.get("tool_calls")
                if isinstance(tool_calls, Sequence) and not isinstance(tool_calls, (str, bytes)):
                    for tool_call in tool_calls:
                        tool_map = _to_mapping(tool_call) or {}
                        function_block = _to_mapping(tool_map.get("function")) or {}
                        arguments = function_block.get("arguments") or function_block.get("input")
                        if isinstance(arguments, str) and arguments.strip():
                            return arguments.strip()
                        if isinstance(arguments, Mapping):
                            return json.dumps(arguments)
                content_value = message_map.get("content")
                if isinstance(content_value, str) and content_value.strip():
                    return content_value.strip()
            return None

        if not app_config.SCHEMA_FUNCTION_FALLBACK:
            return None

        try:
            client = get_client()
            chat_client = getattr(client, "chat", None)
            completions_client = getattr(chat_client, "completions", None)
            create_completion = getattr(completions_client, "create", None)
        except Exception:
            return None

        if create_completion is None:
            return None

        function_payload, function_call = _build_function_tool_from_schema(schema_bundle)
        payload: dict[str, Any] = {
            "model": model,
            "messages": _prepare_messages(messages),
            "functions": [function_payload],
            "function_call": function_call,
            "timeout": OPENAI_REQUEST_TIMEOUT,
        }

        if temperature is not None and model_supports_temperature(model):  # TEMP_SUPPORTED
            payload["temperature"] = float(temperature)
        if max_completion_tokens is not None:
            payload["max_completion_tokens"] = int(max_completion_tokens)

        try:
            response = create_completion(**payload)
        except OpenAIError as error:
            logger_instance.warning(
                "Function-call fallback for %s failed via chat completions: %s",
                context,
                error,
                exc_info=error,
            )
            return None

        content = (_extract_function_payload(response) or _extract_output_text(response) or "").strip()
        if not allow_empty and not content:
            return None

        response_id = _extract_response_id(response)
        usage_block = _extract_usage_block(response) or {}
        usage = {key: _coerce_token_count(value) for key, value in _normalise_usage(usage_block).items()}
        if usage:
            _update_usage_counters(usage, task=task)

        return ResponsesCallResult(
            content=content,
            usage=usage,
            response_id=response_id,
            raw_response=response,
            used_chat_fallback=True,
        )

    try:
        schema_bundle = _build_schema_bundle_from_format(response_format)
        chat_schema = deepcopy(schema_bundle.chat_response_format["json_schema"])
        removed_fields: list[str] = []
        if "strict" in chat_schema:
            chat_schema.pop("strict", None)
            removed_fields.append("json_schema.strict")
        if removed_fields:
            logger_instance.debug(
                "Cleaning Responses-only fields before chat fallback: %s",
                ", ".join(removed_fields),
            )
    except (ResponsesSchemaError, TypeError) as schema_error:
        logger_instance.warning(
            "Unable to run chat fallback for %s due to schema guard: %s",
            context,
            schema_error,
        )
        return None

    if exc is None:
        logger_instance.info("Falling back to chat completions for %s (%s)", context, reason)
    else:
        logger_instance.info(
            "Falling back to chat completions for %s (%s): %s",
            context,
            reason,
            exc,
        )

    function_result = _call_function_schema_fallback(schema_bundle)
    if function_result is not None:
        return function_result

    prepared_messages = _prepare_messages(messages)
    try:
        with temporarily_force_classic_api():
            chat_result = call_chat_api(
                prepared_messages,
                model=model,
                temperature=temperature,
                max_completion_tokens=max_completion_tokens,
                json_schema=chat_schema,
                reasoning_effort=reasoning_effort,
                verbosity=verbosity,
                task=task,
                extra={"_api_mode": "chat"},
                use_response_format=False,
            )
    except Exception as fallback_error:  # pragma: no cover - network/SDK issues
        logger_instance.warning(
            "Classic chat fallback for %s failed: %s",
            context,
            fallback_error,
            exc_info=fallback_error,
        )
        return None

    fallback_content = (chat_result.content or "").strip()
    if not allow_empty and not fallback_content:
        logger_instance.warning(
            "Classic chat fallback for %s returned empty content",
            context,
        )
        return None

    return ResponsesCallResult(
        content=fallback_content,
        usage=dict(chat_result.usage or {}),
        response_id=chat_result.response_id,
        raw_response=chat_result.raw_response,
        used_chat_fallback=True,
    )


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
    """Execute a Responses API call with retries and return the parsed result."""

    schema_bundle = _build_schema_bundle_from_format(response_format)

    prepared_messages = _prepare_messages(
        _inject_verbosity_hint(messages, _resolve_verbosity(verbosity))
    )

    payload: dict[str, Any] = {
        "model": model,
        "input": prepared_messages,
        "timeout": OPENAI_REQUEST_TIMEOUT,
    }

    text_payload = dict(payload.get("text") or {})
    text_payload.pop("type", None)
    text_payload["format"] = deepcopy(schema_bundle.responses_format)
    payload["text"] = text_payload

    if temperature is not None and model_supports_temperature(model):  # TEMP_SUPPORTED
        payload["temperature"] = float(temperature)

    if max_completion_tokens is not None:
        payload["max_output_tokens"] = int(max_completion_tokens)

    if reasoning_effort and model_supports_reasoning(model):
        payload["reasoning"] = {"effort": reasoning_effort}

    max_tries = max(1, int(retries) + 1)

    @retry_with_backoff(
        max_tries=max_tries,
        logger=logger,
        giveup=is_unrecoverable_schema_error,
    )
    def _dispatch() -> Any:
        with tracer.start_as_current_span("openai.responses_call") as span:
            span.set_attribute("llm.model", model)
            span.set_attribute("llm.has_schema", True)
            if "temperature" in payload:
                span.set_attribute("llm.temperature", payload["temperature"])
            if "reasoning" in payload and isinstance(payload["reasoning"], Mapping):
                span.set_attribute("llm.reasoning.effort", payload["reasoning"].get("effort"))
            return get_client().responses.create(**payload)

    try:
        response = _dispatch()
    except BadRequestError as err:
        if "temperature" in payload and _is_temperature_unsupported_error(err):
            logger.warning(
                "Responses model %s rejected temperature; retrying without it.",
                model,
            )
            payload.pop("temperature", None)
            _mark_model_without_temperature(model)
            response = _dispatch()
        else:
            logger.error("Responses API rejected the request: %s", getattr(err, "message", err))
            raise
    except OpenAIError:
        raise

    content = _extract_output_text(response) or ""
    response_id = _extract_response_id(response)
    usage_block = _extract_usage_block(response) or {}
    usage = {key: _coerce_token_count(value) for key, value in _normalise_usage(usage_block).items()}

    if usage:
        _update_usage_counters(usage, task=task)

    return ResponsesCallResult(
        content=content,
        usage=usage,
        response_id=response_id,
        raw_response=response,
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
    fallback_attempted = False

    def _attempt_fallback(reason: str, exc: Exception | None = None) -> ResponsesCallResult | None:
        nonlocal fallback_attempted
        if fallback_attempted:
            return None
        fallback_attempted = True
        active_logger.info(
            "Responses fallback triggered for %s (reason=%s)",
            context,
            reason,
        )
        return _run_chat_fallback(
            messages,
            model=model,
            response_format=response_format,
            logger_instance=active_logger,
            context=context,
            allow_empty=allow_empty,
            verbosity=verbosity,
            temperature=kwargs.get("temperature"),
            max_completion_tokens=kwargs.get("max_completion_tokens"),
            reasoning_effort=kwargs.get("reasoning_effort"),
            task=kwargs.get("task"),
            reason=reason,
            exc=exc,
        )

    try:
        result = call_responses(
            messages,
            model=model,
            response_format=response_format,
            verbosity=verbosity,
            **kwargs,
        )
    except ResponsesSchemaError as exc:
        active_logger.warning(
            "Responses payload guard blocked %s call; triggering chat fallback: %s",
            context,
            exc,
        )
        fallback = _attempt_fallback("schema_guard", exc)
        if fallback is not None:
            return fallback
        active_logger.error("All API attempts failed for %s (schema_guard).", context)
        return None
    except OpenAIError as exc:
        active_logger.warning(
            "Responses API %s failed; triggering chat fallback: %s",
            context,
            exc,
        )
        fallback = _attempt_fallback("api_error", exc)
        if fallback is not None:
            return fallback
        active_logger.error("All API attempts failed for %s (api_error).", context)
        return None
    except Exception as exc:  # pragma: no cover - defensive
        active_logger.warning(
            "Unexpected error during Responses API %s; triggering chat fallback",
            context,
            exc_info=exc,
        )
        fallback = _attempt_fallback("unexpected_error", exc)
        if fallback is not None:
            return fallback
        active_logger.error("All API attempts failed for %s (unexpected_error).", context)
        return None

    content = (result.content or "").strip()
    expects_json = False
    if isinstance(response_format, Mapping):
        format_type = str(response_format.get("type") or "").lower()
        expects_json = format_type == "json_schema" or bool(response_format.get("json_schema"))
    if expects_json and content:
        try:
            json.loads(content)
        except json.JSONDecodeError as exc:
            active_logger.warning(
                "Responses API %s returned invalid JSON; triggering chat fallback.",
                context,
                exc_info=exc,
            )
            fallback = _attempt_fallback("invalid_json", exc)
            if fallback is not None:
                return fallback
            active_logger.error("All API attempts failed for %s (invalid_json).", context)
            return None
    if not allow_empty and not content:
        active_logger.warning(
            "Responses API %s returned empty content; triggering chat fallback",
            context,
        )
        fallback = _attempt_fallback("empty_response")
        if fallback is not None:
            return fallback
        active_logger.error("All API attempts failed for %s (empty_response).", context)
        return None

    result.content = content
    return result


__all__ = [
    "ResponsesCallResult",
    "build_json_schema_format",
    "call_responses",
    "call_responses_safe",
]
