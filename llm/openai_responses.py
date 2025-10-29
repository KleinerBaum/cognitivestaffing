"""Helpers for invoking the OpenAI Responses API with structured outputs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
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

from config import OPENAI_REQUEST_TIMEOUT, STRICT_JSON, ModelTask
from openai_utils.api import (
    _coerce_token_count,
    _extract_output_text,
    _extract_response_id,
    _extract_usage_block,
    _is_temperature_unsupported_error,
    _mark_model_without_temperature,
    _normalise_usage,
    _update_usage_counters,
    get_client,
    model_supports_reasoning,
    model_supports_temperature,
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


def build_json_schema_format(
    *,
    name: str,
    schema: Mapping[str, Any],
    strict: bool | None = None,
) -> dict[str, Any]:
    """Return a ``text.format`` payload for JSON schema outputs."""

    if not isinstance(name, str) or not name.strip():
        raise ValueError("A non-empty schema name is required for response_format.")
    if not isinstance(schema, Mapping):
        raise TypeError("Schema must be a mapping when building response_format.")

    schema_payload = dict(schema)
    format_payload: dict[str, Any] = {
        "type": "json_schema",
        "name": name,
        "schema": schema_payload,
    }
    strict_flag = STRICT_JSON if strict is None else bool(strict)
    if strict_flag:
        format_payload["strict"] = True

    return format_payload


def _prepare_messages(messages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return ``messages`` as a list of plain dictionaries."""

    prepared: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, Mapping):
            raise TypeError("Messages must be mappings when calling the Responses API.")
        prepared.append({str(key): value for key, value in message.items()})
    return prepared


def call_responses(
    messages: Sequence[Mapping[str, Any]],
    *,
    model: str,
    response_format: Mapping[str, Any],
    temperature: float | None = None,
    max_tokens: int | None = None,
    reasoning_effort: str | None = None,
    retries: int = 2,
    task: ModelTask | str | None = None,
) -> ResponsesCallResult:
    """Execute a Responses API call with retries and return the parsed result."""

    if not isinstance(response_format, Mapping):
        raise TypeError("response_format must be a mapping payload.")

    payload: dict[str, Any] = {
        "model": model,
        "input": _prepare_messages(messages),
        "timeout": OPENAI_REQUEST_TIMEOUT,
    }

    text_payload = dict(payload.get("text") or {})
    text_payload["format"] = dict(response_format)
    payload["text"] = text_payload

    if temperature is not None and model_supports_temperature(model):
        payload["temperature"] = float(temperature)

    if max_tokens is not None:
        payload["max_output_tokens"] = int(max_tokens)

    if reasoning_effort and model_supports_reasoning(model):
        payload["reasoning"] = {"effort": reasoning_effort}

    max_tries = max(1, int(retries) + 1)

    @backoff.on_exception(  # type: ignore[misc]
        backoff.expo,
        (APITimeoutError, APIConnectionError, RateLimitError, APIError),
        max_tries=max_tries,
        jitter=backoff.full_jitter,
        logger=logger,
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
    try:
        result = call_responses(
            messages,
            model=model,
            response_format=response_format,
            **kwargs,
        )
    except OpenAIError as exc:
        active_logger.warning(
            "Responses API %s failed; triggering fallback: %s",
            context,
            exc,
        )
        return None
    except Exception as exc:  # pragma: no cover - defensive
        active_logger.warning(
            "Unexpected error during Responses API %s; triggering fallback",
            context,
            exc_info=exc,
        )
        return None

    content = (result.content or "").strip()
    if not allow_empty and not content:
        active_logger.warning(
            "Responses API %s returned empty content; triggering fallback",
            context,
        )
        return None

    return result


__all__ = [
    "ResponsesCallResult",
    "build_json_schema_format",
    "call_responses",
    "call_responses_safe",
]
