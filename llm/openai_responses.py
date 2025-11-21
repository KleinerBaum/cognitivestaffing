"""Helpers for invoking the OpenAI Responses API with structured outputs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from copy import deepcopy
from typing import Any, Mapping, Sequence

import backoff
from opentelemetry import trace
from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    BadRequestError,
    OpenAIError,
    RateLimitError,
)

from config import OPENAI_REQUEST_TIMEOUT, ModelTask, temporarily_force_classic_api
from openai_utils.api import (
    _coerce_token_count,
    _extract_output_text,
    _extract_response_id,
    _extract_usage_block,
    _is_temperature_unsupported_error,
    _mark_model_without_temperature,
    _normalise_usage,
    _update_usage_counters,
    build_schema_format_bundle,
    call_chat_api,
    get_client,
    is_unrecoverable_schema_error,
    model_supports_reasoning,
    model_supports_temperature,
    SchemaFormatBundle,
)

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

    schema_payload = guard_no_additional_properties(_prune_unsupported_formats(deepcopy(dict(schema))))
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
    if json_schema_payload is None:
        raise ResponsesSchemaError("Responses payload requires a schema. [RESPONSES_PAYLOAD_GUARD]")
    if not isinstance(json_schema_payload, Mapping):
        raise TypeError("response_format['json_schema'] must be a mapping payload.")

    schema_payload = json_schema_payload.get("schema")
    if schema_payload is None:
        raise ResponsesSchemaError("Responses payload requires a schema. [RESPONSES_PAYLOAD_GUARD]")
    if not isinstance(schema_payload, Mapping):
        raise TypeError("response_format['json_schema']['schema'] must be a mapping payload.")

    schema_name = json_schema_payload.get("name")
    if not isinstance(schema_name, str) or not schema_name.strip():
        raise ResponsesSchemaError("Responses payload requires a schema name. [RESPONSES_PAYLOAD_GUARD]")
    schema_name = schema_name.strip()

    schema_config: dict[str, Any] = {"name": schema_name, "schema": schema_payload}
    if "strict" in json_schema_payload:
        schema_config["strict"] = json_schema_payload.get("strict")

    return build_schema_format_bundle(schema_config)


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
    task: ModelTask | str | None,
    reason: str,
    exc: Exception | None,
) -> ResponsesCallResult | None:
    """Fallback to the classic chat API and return a :class:`ResponsesCallResult`."""

    try:
        schema_bundle = _build_schema_bundle_from_format(response_format)
        chat_schema = deepcopy(schema_bundle.chat_response_format["json_schema"])
        chat_schema.pop("strict", None)
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
                task=task,
                extra={"_api_mode": "chat"},
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
    retries: int = 2,
    task: ModelTask | str | None = None,
) -> ResponsesCallResult:
    """Execute a Responses API call with retries and return the parsed result."""

    schema_bundle = _build_schema_bundle_from_format(response_format)

    payload: dict[str, Any] = {
        "model": model,
        "input": _prepare_messages(messages),
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

    @backoff.on_exception(  # type: ignore[misc]
        backoff.expo,
        (APITimeoutError, APIConnectionError, RateLimitError, APIError),
        max_tries=max_tries,
        jitter=backoff.full_jitter,
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
            **kwargs,
        )
    except ResponsesSchemaError as exc:
        active_logger.warning(
            "Responses payload guard blocked %s call; triggering chat fallback: %s",
            context,
            exc,
        )
        return _attempt_fallback("schema_guard", exc)
    except OpenAIError as exc:
        active_logger.warning(
            "Responses API %s failed; triggering chat fallback: %s",
            context,
            exc,
        )
        fallback = _attempt_fallback("api_error", exc)
        return fallback
    except Exception as exc:  # pragma: no cover - defensive
        active_logger.warning(
            "Unexpected error during Responses API %s; triggering chat fallback",
            context,
            exc_info=exc,
        )
        fallback = _attempt_fallback("unexpected_error", exc)
        return fallback

    content = (result.content or "").strip()
    if not allow_empty and not content:
        active_logger.warning(
            "Responses API %s returned empty content; triggering chat fallback",
            context,
        )
        fallback = _attempt_fallback("empty_response")
        if fallback is not None:
            return fallback
        return None

    result.content = content
    return result


__all__ = [
    "ResponsesCallResult",
    "build_json_schema_format",
    "call_responses",
    "call_responses_safe",
]
