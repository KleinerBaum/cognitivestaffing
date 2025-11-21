"""OpenAI API client and chat helpers.

This module isolates low-level interactions with the OpenAI Responses and
Chat Completions APIs. It provides a :func:`call_chat_api` helper that also
executes any requested function tools and feeds the results back to the
model, effectively acting as a small agent loop regardless of the selected
endpoint.
"""

from __future__ import annotations

import json
import logging
import re
from copy import deepcopy
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from difflib import SequenceMatcher
from threading import Lock
from typing import Any, Callable, Dict, Final, Iterable, Iterator, Mapping, Optional, Sequence, cast

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    OpenAI,
    OpenAIError,
    RateLimitError,
)
import streamlit as st
from prompts import prompt_registry

import config as app_config
from config import (
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_ORGANIZATION,
    OPENAI_PROJECT,
    OPENAI_REQUEST_TIMEOUT,
    REASONING_EFFORT,
    STRICT_JSON,
    VERBOSITY,
    ModelTask,
    get_active_verbosity,
    get_first_available_model,
    get_model_candidates,
    is_model_available,
    mark_model_unavailable,
    normalise_verbosity,
    select_model,
)
from constants.keys import StateKeys
from llm.cost_router import PromptCostEstimate, route_model_for_messages
from utils.errors import display_error, resolve_message
from utils.llm_state import llm_disabled_message
from utils.retry import retry_with_backoff
from .client import (
    FileSearchKey,
    FileSearchResult,
    ResponsesRequest,
    RetryState,
    ToolCallPayload,
    ToolMessagePayload,
    UsageDict,
    build_fallback_context,
    create_retry_state,
)

logger = logging.getLogger("cognitive_needs.openai")
tracer = trace.get_tracer(__name__)

# Global client instance (monkeypatchable in tests)
client: OpenAI | None = None


_REASONING_MODEL_PATTERN = re.compile(r"^o\d")
_MODELS_WITHOUT_TEMPERATURE: set[str] = set()
_MODELS_WITHOUT_REASONING: set[str] = set()
_USAGE_LOCK = Lock()


@lru_cache(maxsize=1)
def _need_analysis_schema() -> dict[str, Any]:
    """Return cached NeedAnalysis schema for Responses structured output."""

    from core.schema import build_need_analysis_responses_schema

    return build_need_analysis_responses_schema()


def _sanitize_json_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Validate ``schema`` for Responses usage without circular imports."""

    from core.schema import ensure_responses_json_schema

    return ensure_responses_json_schema(schema)


@dataclass(frozen=True)
class SchemaFormatBundle:
    """Container describing schema payloads for both OpenAI APIs."""

    name: str
    schema: dict[str, Any]
    strict: bool | None
    chat_response_format: dict[str, Any]
    responses_format: dict[str, Any]


def build_schema_format_bundle(json_schema_payload: Mapping[str, Any]) -> SchemaFormatBundle:
    """Return normalised schema payloads for chat and Responses requests."""

    if not isinstance(json_schema_payload, Mapping):
        raise TypeError("json_schema payload must be a mapping")

    schema_name_candidate = json_schema_payload.get("name")
    schema_name = str(schema_name_candidate or "").strip()
    if not schema_name:
        raise ValueError("json_schema payload requires a non-empty 'name'.")

    schema_body = json_schema_payload.get("schema")
    if not isinstance(schema_body, Mapping):
        raise ValueError("json_schema payload requires a mapping 'schema'.")

    strict_override = json_schema_payload.get("strict") if "strict" in json_schema_payload else None
    strict_value = STRICT_JSON if strict_override is None else bool(strict_override)

    sanitized_schema = deepcopy(_sanitize_json_schema(schema_body))

    chat_format: dict[str, Any] = {
        "type": "json_schema",
        "json_schema": {
            "name": schema_name,
            "schema": deepcopy(sanitized_schema),
        },
    }

    responses_format: dict[str, Any] = {
        "type": "json_schema",
        "name": schema_name,
        "schema": deepcopy(sanitized_schema),
        "json_schema": {
            "name": schema_name,
            "schema": deepcopy(sanitized_schema),
        },
    }

    if strict_value:
        chat_format["json_schema"]["strict"] = strict_value
        chat_format["strict"] = strict_value
        responses_format["strict"] = strict_value
        responses_format["json_schema"]["strict"] = strict_value

    return SchemaFormatBundle(
        name=schema_name,
        schema=sanitized_schema,
        strict=strict_value if strict_value else None,
        chat_response_format=chat_format,
        responses_format=responses_format,
    )


def build_need_analysis_json_schema_payload() -> dict[str, Any]:
    """Return the JSON schema payload for need analysis responses.

    The payload is used for both Chat Completions and Responses requests and
    always includes the canonical schema name.  # RESPONSES_V2025_SCHEMA_FIX
    """

    return {
        "name": "need_analysis_profile",
        "schema": deepcopy(_need_analysis_schema()),
    }


_MISSING_API_KEY_ALERT_STATE_KEY = "system.openai.api_key_missing_alert"
_MISSING_API_KEY_ALERT_MESSAGE: Final[tuple[str, str]] = (
    "\U0001f511 OpenAI-API-Schlüssel fehlt. Bitte `OPENAI_API_KEY` in der Umgebung oder in den Streamlit-Secrets hinterlegen.",
    "\U0001f511 OpenAI API key missing. Please set `OPENAI_API_KEY` via environment variable or Streamlit secrets.",
)
_MISSING_API_KEY_RUNTIME_MESSAGE: Final[tuple[str, str]] = (
    "OpenAI-API-Schlüssel nicht konfiguriert. Setze OPENAI_API_KEY in der Umgebung oder in den Streamlit-Secrets.",
    "OpenAI API key not configured. Set OPENAI_API_KEY in the environment or Streamlit secrets.",
)

_AUTHENTICATION_ERROR_MESSAGE: Final[tuple[str, str]] = (
    "OpenAI-API-Schlüssel ungültig oder Kontingent aufgebraucht.",
    "OpenAI API key invalid or quota exceeded.",
)
_RATE_LIMIT_ERROR_MESSAGE: Final[tuple[str, str]] = (
    "OpenAI-API-Rate-Limit erreicht. Bitte später erneut versuchen.",
    "OpenAI API rate limit exceeded. Please retry later.",
)


def _llm_disabled() -> bool:
    """Return ``True`` when API calls should be blocked due to missing credentials."""

    if not OPENAI_API_KEY:
        return True
    try:
        return bool(st.session_state.get("openai_api_key_missing"))
    except Exception:  # pragma: no cover - Streamlit not initialised
        return False


_NETWORK_ERROR_MESSAGE: Final[tuple[str, str]] = (
    "Netzwerkfehler bei der Kommunikation mit OpenAI. Bitte Verbindung prüfen und erneut versuchen.",
    "Network error communicating with OpenAI. Please check your connection and retry.",
)
_INVALID_REQUEST_ERROR_MESSAGE: Final[tuple[str, str]] = (
    "❌ Interner Fehler bei der Verarbeitung der Anfrage. (Die App hat eine ungültige Anfrage an das KI-Modell gesendet.)",
    "❌ An internal error occurred while processing your request. (The app made an invalid request to the AI model.)",
)


_VERBOSITY_CONFIG: dict[str, str] = prompt_registry.get("openai_utils.api.verbosity")
_VERBOSITY_FORMAT_GUARD = _VERBOSITY_CONFIG["format_guard"]
_VERBOSITY_HINTS = {level: hint for level, hint in _VERBOSITY_CONFIG.items() if level != "format_guard"}


def _resolve_verbosity(value: Optional[str]) -> str:
    """Return the active verbosity preference for the current session."""

    if value is None:
        return get_active_verbosity()
    return normalise_verbosity(value, default=VERBOSITY)


def _inject_verbosity_hint(
    messages: Sequence[Mapping[str, Any]],
    level: str,
) -> list[dict[str, Any]]:
    """Return ``messages`` with an additional system hint for ``level``."""

    hint = _VERBOSITY_HINTS.get(level)
    if not hint:
        return [dict(message) for message in messages]

    instruction = f"{hint}\n{_VERBOSITY_FORMAT_GUARD}".strip()

    new_messages: list[dict[str, Any]] = []
    inserted = False
    for message in messages:
        new_messages.append(dict(message))
        role = str(message.get("role", "")).strip().lower()
        if not inserted and role == "system":
            new_messages.append({"role": "system", "content": instruction})
            inserted = True

    if not inserted:
        new_messages.insert(0, {"role": "system", "content": instruction})

    return new_messages


def _normalise_model_name(model: Optional[str]) -> str:
    """Return ``model`` as a lower-cased identifier without surrounding whitespace."""

    if not model:
        return ""
    return model.strip().lower()


def _mark_model_without_temperature(model: Optional[str]) -> None:
    """Remember that ``model`` rejects the ``temperature`` parameter."""

    normalized = _normalise_model_name(model)
    if normalized:
        _MODELS_WITHOUT_TEMPERATURE.add(normalized)


def _mark_model_without_reasoning(model: Optional[str]) -> None:
    """Remember that ``model`` rejects the ``reasoning`` parameter."""

    normalized = _normalise_model_name(model)
    if normalized:
        _MODELS_WITHOUT_REASONING.add(normalized)


def model_supports_reasoning(model: Optional[str]) -> bool:
    """Return ``True`` if ``model`` accepts a reasoning payload.

    OpenAI exposes the explicit ``reasoning`` parameter only on the dedicated
    reasoning-capable families (``o1`` variants and names containing the
    ``reasoning`` suffix). We heuristically detect those models to avoid
    sending the parameter to regular chat models that would reject it.
    """

    normalized = _normalise_model_name(model)
    if not normalized:
        return False
    if normalized in _MODELS_WITHOUT_REASONING:
        return False
    if _REASONING_MODEL_PATTERN.match(normalized):
        return True
    return "reasoning" in normalized


def model_supports_temperature(model: Optional[str]) -> bool:
    """Return ``True`` if ``model`` accepts a temperature parameter.

    The OpenAI reasoning models (``o1`` family and related previews) reject the
    ``temperature`` argument. To keep compatibility across models, we detect
    those names heuristically and omit the parameter when necessary.
    """

    normalized = _normalise_model_name(model)
    if not normalized:
        return True
    if normalized in _MODELS_WITHOUT_TEMPERATURE:
        return False
    if model_supports_reasoning(model):
        return False
    return "reasoning" not in normalized


def _should_mark_model_unavailable(error: OpenAIError) -> bool:
    """Return ``True`` if ``error`` indicates the selected model is unavailable."""

    code = getattr(error, "code", "") or getattr(getattr(error, "error", {}), "code", "")
    if isinstance(code, str):
        lowered_code = code.lower()
        if lowered_code in {"model_not_found", "model_not_available", "invalid_model"}:
            return True
    message = getattr(error, "message", str(error))
    lowered = message.lower()
    if "model" not in lowered:
        return False
    phrases = [
        "does not exist",
        "not found",
        "currently unavailable",
        "currently overloaded",
        "was not found",
        "has been deprecated",
        "is not available",
    ]
    return any(phrase in lowered for phrase in phrases)


def _message_indicates_parameter_unsupported(message: str, parameter: str) -> bool:
    """Return ``True`` if ``message`` clearly rejects ``parameter``."""

    lowered = message.lower()
    if parameter not in lowered:
        return False
    return any(
        phrase in lowered
        for phrase in (
            "unsupported parameter",
            "does not support",
            "not supported",
            "cannot be used",
        )
    )


def _value_matches_parameter(value: Any, parameter: str) -> bool:
    """Return ``True`` if ``value`` names ``parameter`` (allowing dotted paths)."""

    if not isinstance(value, str):
        return False
    lowered_value = value.strip().lower()
    return lowered_value == parameter or lowered_value.endswith(f".{parameter}")


def _iter_error_payloads(error: OpenAIError) -> Iterator[Mapping[str, Any]]:
    """Yield mapping payloads attached to ``error`` (including nested details)."""

    stack: list[Mapping[str, Any]] = []
    for attr in ("error", "body"):
        value = getattr(error, attr, None)
        if isinstance(value, Mapping):
            stack.append(value)
    seen: set[int] = set()
    while stack:
        payload = stack.pop()
        payload_id = id(payload)
        if payload_id in seen:
            continue
        seen.add(payload_id)
        yield payload
        nested = payload.get("error")
        if isinstance(nested, Mapping):
            stack.append(nested)
        details = payload.get("details")
        if isinstance(details, Sequence) and not isinstance(details, (str, bytes)):
            for item in details:
                if isinstance(item, Mapping):
                    stack.append(item)


def _is_parameter_unsupported_error(error: OpenAIError, parameter: str) -> bool:
    """Return ``True`` if ``error`` indicates the model rejected ``parameter``."""

    parameter = parameter.lower()
    message = getattr(error, "message", str(error))
    if isinstance(message, str) and _message_indicates_parameter_unsupported(message, parameter):
        return True
    error_text = str(error)
    if error_text != message and _message_indicates_parameter_unsupported(error_text, parameter):
        return True

    for payload in _iter_error_payloads(error):
        payload_message = payload.get("message")
        if isinstance(payload_message, str) and _message_indicates_parameter_unsupported(payload_message, parameter):
            return True
        code = payload.get("code")
        if isinstance(code, str) and code.lower() == "unsupported_parameter":
            for key in ("param", "parameter", "field", "name"):
                if _value_matches_parameter(payload.get(key), parameter):
                    return True
    return False


def _is_temperature_unsupported_error(error: OpenAIError) -> bool:
    """Return ``True`` if ``error`` indicates the model rejected ``temperature``."""

    return _is_parameter_unsupported_error(error, "temperature")


def _is_reasoning_unsupported_error(error: OpenAIError) -> bool:
    """Return ``True`` if ``error`` indicates the model rejected ``reasoning``."""

    return _is_parameter_unsupported_error(error, "reasoning")


def _message_indicates_unrecoverable_schema(message: str) -> bool:
    """Return ``True`` if ``message`` signals an unrecoverable schema issue."""

    lowered = message.lower()
    if "invalid_json_schema" in lowered or "invalid json schema" in lowered:
        return True
    if "missing required" in lowered and "schema" in lowered:
        return True
    return False


def is_unrecoverable_schema_error(error: Exception) -> bool:
    """Return ``True`` when ``error`` should stop retries due to schema issues."""

    if not isinstance(error, APIError):
        return False

    message = getattr(error, "message", str(error))
    if isinstance(message, str) and _message_indicates_unrecoverable_schema(message):
        return True

    for payload in _iter_error_payloads(error):
        code = payload.get("code")
        if isinstance(code, str) and code.lower() == "invalid_json_schema":
            return True
        payload_message = payload.get("message")
        if isinstance(payload_message, str) and _message_indicates_unrecoverable_schema(payload_message):
            return True

    return False


def _prune_payload_for_api_mode(payload: Mapping[str, Any], api_mode: str) -> dict[str, Any]:
    """Return ``payload`` without fields unsupported by ``api_mode``.

    The helper normalises message keys and strips obviously invalid fields so we
    avoid OpenAI ``invalid_request_error`` or ``invalid_json_schema`` responses
    before the request leaves the application. This keeps retries from
    repeatedly submitting malformed payloads.
    """

    cleaned = dict(payload)
    removed: list[str] = []

    for key in list(cleaned):
        if key.startswith("_"):
            removed.append(key)
            cleaned.pop(key, None)

    mode = api_mode if api_mode in {"chat", "responses"} else "responses"

    if mode == "chat":
        if "input" in cleaned and "messages" not in cleaned and isinstance(cleaned["input"], Sequence):
            cleaned["messages"] = cleaned["input"]
        for invalid_field in ("input", "text", "previous_response_id", "max_output_tokens"):
            if invalid_field in cleaned:
                removed.append(invalid_field)
                cleaned.pop(invalid_field, None)
    else:
        if "messages" in cleaned and "input" not in cleaned:
            cleaned["input"] = cleaned.pop("messages")
        for invalid_field in ("functions", "function_call", "max_completion_tokens"):
            if invalid_field in cleaned:
                removed.append(invalid_field)
                cleaned.pop(invalid_field, None)
        if "response_format" in cleaned:
            cleaned.pop("response_format")
            removed.append("response_format")

    if removed:
        logger.debug(
            "Pruned unsupported fields for %s API payload: %s",
            mode,
            ", ".join(sorted(set(removed))),
        )

    return cleaned


def _log_known_openai_error(error: OpenAIError, *, api_mode: str) -> None:
    """Record additional context for known, non-retriable OpenAI failures."""

    if is_unrecoverable_schema_error(error):
        logger.error(
            "OpenAI rejected JSON schema for %s request; skipping retries: %s",
            api_mode,
            getattr(error, "message", str(error)),
        )


def _create_response_with_timeout(payload: Dict[str, Any], *, api_mode: str | None = None) -> Any:
    """Execute a Responses create call with configured timeout handling."""

    request_kwargs = dict(payload)
    api_mode = api_mode or request_kwargs.pop("_api_mode", None)
    timeout = request_kwargs.pop("timeout", OPENAI_REQUEST_TIMEOUT)
    mode = api_mode or ("chat" if app_config.USE_CLASSIC_API else "responses")
    cleaned_payload = _prune_payload_for_api_mode(request_kwargs, mode)
    if mode == "chat":
        return get_client().chat.completions.create(timeout=timeout, **cleaned_payload)
    return get_client().responses.create(timeout=timeout, **cleaned_payload)


def _execute_response(payload: Dict[str, Any], model: Optional[str], *, api_mode: str | None = None) -> Any:
    """Send ``payload`` to the configured OpenAI API with retry handling."""

    with tracer.start_as_current_span("openai.execute_response") as span:
        mode = api_mode or ("chat" if app_config.USE_CLASSIC_API else "responses")
        if model:
            span.set_attribute("llm.model", model)
        span.set_attribute("llm.has_tools", "functions" in payload or "tools" in payload)
        if "temperature" in payload:
            temperature_value = payload.get("temperature")
            if isinstance(temperature_value, (int, float)):
                span.set_attribute("llm.temperature", float(temperature_value))
            elif temperature_value is not None:
                span.set_attribute("llm.temperature", str(temperature_value))
        try:
            return _create_response_with_timeout(payload, api_mode=api_mode)
        except BadRequestError as err:
            span.record_exception(err)
            _log_known_openai_error(err, api_mode=mode)
            if "temperature" in payload and _is_temperature_unsupported_error(err):
                span.add_event("retry_without_temperature")
                _mark_model_without_temperature(model)
                payload.pop("temperature", None)
                return _create_response_with_timeout(payload, api_mode=api_mode)
            if "reasoning" in payload and _is_reasoning_unsupported_error(err):
                span.add_event("retry_without_reasoning")
                _mark_model_without_reasoning(model)
                payload.pop("reasoning", None)
                return _create_response_with_timeout(payload, api_mode=api_mode)
            if model and _should_mark_model_unavailable(err):
                mark_model_unavailable(model)
            span.set_status(Status(StatusCode.ERROR, str(err)))
            raise
        except OpenAIError as err:
            span.record_exception(err)
            _log_known_openai_error(err, api_mode=mode)
            if model and _should_mark_model_unavailable(err):
                mark_model_unavailable(model)
            span.set_status(Status(StatusCode.ERROR, str(err)))
            raise


def _to_mapping(item: Any) -> dict[str, Any] | None:
    """Best-effort conversion of SDK dataclasses to Python dictionaries."""

    if isinstance(item, Mapping):
        return dict(item)
    for attr in ("model_dump", "dict"):
        method = getattr(item, attr, None)
        if callable(method):
            try:
                value = method()
            except TypeError:
                try:
                    value = method(mode="python")
                except TypeError:
                    continue
            if isinstance(value, Mapping):
                return dict(value)
    data = getattr(item, "__dict__", None)
    if isinstance(data, Mapping):
        return dict(data)
    return None


def _dump_json(value: Any) -> Optional[str]:
    """Serialise ``value`` to JSON, tolerating dataclass-style inputs."""

    if value is None:
        return None
    try:
        return json.dumps(value)
    except TypeError:
        try:
            mapping = _to_mapping(value)
        except Exception:  # pragma: no cover - defensive
            mapping = None
        if mapping is not None:
            try:
                return json.dumps(mapping)
            except TypeError:
                return str(mapping)
        return str(value)


def _extract_chat_completion_text(response_obj: Any) -> Optional[str]:
    """Return text content from a Chat Completions style response."""

    choices = getattr(response_obj, "choices", None)
    if choices is None:
        response_map = _to_mapping(response_obj)
        choices = response_map.get("choices") if response_map else None

    if not isinstance(choices, Sequence) or isinstance(choices, (str, bytes)):
        return None

    parts: list[str] = []

    for choice in choices:
        choice_map = _to_mapping(choice)
        if not choice_map:
            continue
        message_map = _to_mapping(choice_map.get("message"))
        if not message_map:
            continue

        parsed_value = message_map.get("parsed")
        if parsed_value is not None:
            dumped = _dump_json(parsed_value)
            if dumped:
                parts.append(dumped)
                continue

        content_value = message_map.get("content")
        if isinstance(content_value, str):
            if content_value:
                parts.append(content_value)
            continue
        if isinstance(content_value, Sequence) and not isinstance(content_value, (str, bytes)):
            for segment in content_value:
                segment_map = _to_mapping(segment)
                if not segment_map:
                    continue
                if segment_map.get("text"):
                    parts.append(str(segment_map["text"]))
                elif segment_map.get("json") is not None:
                    dumped = _dump_json(segment_map.get("json"))
                    if dumped:
                        parts.append(dumped)

    joined = "\n".join(part for part in parts if part)
    return joined or None


def _extract_output_text(response_obj: Any) -> Optional[str]:
    """Return concatenated text from an OpenAI response object."""

    text = getattr(response_obj, "output_text", None)
    if text:
        return text
    chunks: list[str] = []
    for raw_item in getattr(response_obj, "output", []) or []:
        item_dict = _to_mapping(raw_item)
        if not item_dict:
            continue
        item_type = item_dict.get("type")
        json_value = item_dict.get("json")
        if json_value is not None:
            dumped = _dump_json(json_value)
            if dumped:
                chunks.append(dumped)
        contents = item_dict.get("content")
        if isinstance(contents, Sequence) and not isinstance(contents, (str, bytes)):
            iterable: Iterable[Any] = contents
        else:
            iterable = []
        if item_type == "message" and iterable:
            for raw_content in iterable:
                content_dict = _to_mapping(raw_content)
                if not content_dict:
                    continue
                json_value = content_dict.get("json")
                if json_value is not None:
                    dumped = _dump_json(json_value)
                    if dumped:
                        chunks.append(dumped)
                text_value = content_dict.get("text")
                if text_value:
                    chunks.append(str(text_value))
        else:
            text_value = item_dict.get("text")
            if text_value:
                chunks.append(str(text_value))
            for raw_content in iterable:
                content_dict = _to_mapping(raw_content)
                if not content_dict:
                    continue
                json_value = content_dict.get("json")
                if json_value is not None:
                    dumped = _dump_json(json_value)
                    if dumped:
                        chunks.append(dumped)
                text_value = content_dict.get("text")
                if text_value:
                    chunks.append(str(text_value))
    if chunks:
        return "\n".join(chunk for chunk in chunks if chunk)
    chat_text = _extract_chat_completion_text(response_obj)
    if chat_text:
        return chat_text
    fallback = _chat_content(response_obj)
    if fallback:
        return fallback
    return text


def _normalise_usage(usage_obj: Any) -> Mapping[str, Any]:
    """Return a plain dictionary describing token usage."""

    if usage_obj and not isinstance(usage_obj, dict):
        usage: Mapping[str, Any] = getattr(usage_obj, "model_dump", getattr(usage_obj, "dict", lambda: {}))()
    elif isinstance(usage_obj, Mapping):
        usage = usage_obj
    else:
        usage = {}

    normalised = dict(usage)
    prompt_tokens = normalised.get("prompt_tokens")
    completion_tokens = normalised.get("completion_tokens")
    total_tokens = normalised.get("total_tokens")

    if prompt_tokens is not None and "input_tokens" not in normalised:
        normalised["input_tokens"] = prompt_tokens
    if completion_tokens is not None and "output_tokens" not in normalised:
        normalised["output_tokens"] = completion_tokens
    if total_tokens is not None and "total_tokens" not in normalised:
        normalised["total_tokens"] = total_tokens

    return normalised


def _numeric_usage(usage: Mapping[str, Any]) -> UsageDict:
    """Return ``usage`` with token counts coerced to integers."""

    numeric: UsageDict = {}
    for key, value in usage.items():
        numeric[str(key)] = _coerce_token_count(value)
    return numeric


def _extract_usage_block(response: Any) -> Any:
    """Return the raw usage block from an OpenAI response object."""

    usage = getattr(response, "usage", None)
    if usage is not None:
        return usage
    response_map = _to_mapping(response)
    if response_map is not None:
        return response_map.get("usage")
    return None


def _extract_response_id(response: Any) -> str | None:
    """Return the identifier assigned to an OpenAI response."""

    identifier = getattr(response, "id", None)
    if isinstance(identifier, str) and identifier.strip():
        return identifier.strip()
    response_map = _to_mapping(response)
    if response_map is not None:
        value = response_map.get("id")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _coerce_token_count(value: Any) -> int:
    """Return an integer token count extracted from ``value``."""

    if value is None:
        return 0
    if isinstance(value, Mapping):
        for key in ("total", "total_tokens", "value", "tokens"):
            if key in value:
                nested = _coerce_token_count(value[key])
                if nested:
                    return nested
        total = 0
        for nested_value in value.values():
            total += _coerce_token_count(nested_value)
        return total
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        total = 0
        for item in value:
            total += _coerce_token_count(item)
        return total
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _normalise_task(task: ModelTask | str | None) -> str:
    """Return a normalised identifier for ``task`` suitable for metrics."""

    if isinstance(task, ModelTask):
        return task.value
    if isinstance(task, str) and task.strip():
        return task.strip()
    return ModelTask.DEFAULT.value


def _update_usage_counters(usage: Mapping[str, Any], *, task: ModelTask | str | None) -> None:
    """Accumulate token usage in the Streamlit session state."""

    if StateKeys.USAGE not in st.session_state:
        return

    with _USAGE_LOCK:
        usage_state = st.session_state[StateKeys.USAGE]
        input_tokens = _coerce_token_count(usage.get("input_tokens"))
        output_tokens = _coerce_token_count(usage.get("output_tokens"))

        usage_state["input_tokens"] = _coerce_token_count(usage_state.get("input_tokens", 0)) + input_tokens
        usage_state["output_tokens"] = _coerce_token_count(usage_state.get("output_tokens", 0)) + output_tokens

        task_key = _normalise_task(task)
        task_map = usage_state.setdefault("by_task", {})
        task_totals = task_map.setdefault(task_key, {"input": 0, "output": 0})
        task_totals["input"] = _coerce_token_count(task_totals.get("input", 0)) + input_tokens
        task_totals["output"] = _coerce_token_count(task_totals.get("output", 0)) + output_tokens


def _accumulate_usage(state: RetryState, latest: UsageDict) -> None:
    """Add ``latest`` token counts to ``state``."""

    for key, value in latest.items():
        state.accumulated_usage[key] = state.accumulated_usage.get(key, 0) + value


def _usage_snapshot(state: RetryState, latest: UsageDict) -> UsageDict:
    """Return the merged usage totals after accounting for retries."""

    if state.accumulated_usage:
        return dict(state.accumulated_usage)
    return dict(latest)


def _serialise_tool_payload(value: Any) -> str | None:
    """Return ``value`` as a JSON string if possible."""

    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value)
    except TypeError:
        return None


def _collect_tool_calls_from_chat_completion(response: Any) -> list[ToolCallPayload]:
    """Extract tool calls from a Chat Completions response."""

    choices = getattr(response, "choices", None)
    if choices is None:
        response_map = _to_mapping(response)
        choices = response_map.get("choices") if response_map else None

    if not isinstance(choices, Sequence) or isinstance(choices, (str, bytes)):
        return []

    collected: list[ToolCallPayload] = []
    seen_ids: set[str] = set()

    for choice in choices:
        choice_map = _to_mapping(choice)
        if not choice_map:
            continue
        message_map = _to_mapping(choice_map.get("message"))
        if not message_map:
            continue

        raw_tool_calls = message_map.get("tool_calls")
        if isinstance(raw_tool_calls, Sequence) and not isinstance(raw_tool_calls, (str, bytes)):
            for raw_call in raw_tool_calls:
                call_map = _to_mapping(raw_call)
                if not call_map:
                    continue

                function_payload = _to_mapping(call_map.get("function")) or {}
                normalised_function = dict(function_payload)
                name_value = normalised_function.get("name") or call_map.get("name")
                if isinstance(name_value, str) and name_value.strip():
                    normalised_function["name"] = name_value.strip()

                arguments_value: str | None = None
                for candidate in (
                    normalised_function.get("arguments"),
                    call_map.get("arguments"),
                ):
                    serialised = _serialise_tool_payload(candidate)
                    if serialised is not None:
                        arguments_value = serialised
                        break
                if arguments_value is not None:
                    normalised_function["arguments"] = arguments_value
                    normalised_function["input"] = arguments_value

                canonical_id = call_map.get("id") or call_map.get("tool_call_id")
                if isinstance(canonical_id, str) and canonical_id.strip():
                    call_id = canonical_id.strip()
                else:
                    call_id = f"tool_call_{len(collected)}"

                if call_id in seen_ids:
                    continue
                seen_ids.add(call_id)

                payload: ToolCallPayload = {
                    "type": "tool_call",
                    "id": call_id,
                    "call_id": call_id,
                    "name": normalised_function.get("name"),
                    "function": normalised_function,
                }
                collected.append(payload)

        function_call = message_map.get("function_call")
        if function_call:
            call_map = _to_mapping(function_call) or {}
            name_value = call_map.get("name")
            if isinstance(name_value, str) and name_value.strip():
                arguments_value = _serialise_tool_payload(call_map.get("arguments"))
                call_id = call_map.get("id") or name_value.strip()
                if not isinstance(call_id, str) or not call_id.strip():
                    call_id = f"function_call_{len(collected)}"
                if call_id not in seen_ids:
                    seen_ids.add(call_id)
                    function_payload = {"name": name_value.strip()}
                    if arguments_value is not None:
                        function_payload["arguments"] = arguments_value
                        function_payload["input"] = arguments_value
                    collected.append(
                        {
                            "type": "tool_call",
                            "id": call_id,
                            "call_id": call_id,
                            "name": function_payload.get("name"),
                            "function": function_payload,
                        }
                    )

    return collected


def _collect_tool_calls(response: Any) -> list[ToolCallPayload]:
    """Extract tool call payloads from an OpenAI response object."""

    if hasattr(response, "choices") or (isinstance(response, Mapping) and "choices" in response):
        return _collect_tool_calls_from_chat_completion(response)

    tool_calls: list[ToolCallPayload] = []
    for item in getattr(response, "output", []) or []:
        data = _to_mapping(item)
        if not data:
            continue
        typ = str(data.get("type") or "")
        if not typ or ("tool_call" not in typ and "tool_response" not in typ):
            continue

        call_data: ToolCallPayload = cast(ToolCallPayload, dict(data))
        canonical_id = call_data.get("call_id") or call_data.get("id")

        if "tool_response" in typ:
            payload_value: str | None = None
            for candidate in (
                call_data.get("output"),
                call_data.get("content"),
                call_data.get("result"),
            ):
                payload_value = _serialise_tool_payload(candidate)
                if payload_value is not None:
                    break

            if payload_value is not None:
                call_data["output"] = payload_value
                call_data["content"] = payload_value
        else:
            function_payload = call_data.get("function")
            if isinstance(function_payload, Mapping):
                normalised_function: dict[str, Any] = dict(function_payload)
            else:
                normalised_function = {}

            if not normalised_function.get("name") and call_data.get("name"):
                normalised_function["name"] = call_data.get("name")

            function_payload_value: str | None = None
            for candidate in (
                normalised_function.get("input"),
                call_data.get("input"),
                normalised_function.get("arguments"),
                call_data.get("arguments"),
            ):
                function_payload_value = _serialise_tool_payload(candidate)
                if function_payload_value is not None:
                    break

            if function_payload_value is not None:
                normalised_function["input"] = function_payload_value
                normalised_function["arguments"] = function_payload_value

            call_data["function"] = normalised_function

        if canonical_id is not None:
            call_data["call_id"] = str(canonical_id)
        tool_calls.append(call_data)
    return tool_calls


def _execute_tool_invocations(
    tool_calls: Sequence[ToolCallPayload],
    *,
    tool_functions: Mapping[str, Callable[..., Any]] | None,
) -> tuple[list[ToolMessagePayload], bool]:
    """Return tool response messages emitted after executing ``tool_calls``."""

    executed = False
    tool_messages: list[ToolMessagePayload] = []

    for call in tool_calls:
        call_type = str(call.get("type") or "")
        call_identifier = call.get("call_id") or call.get("id")
        tool_identifier = str(call_identifier or "tool_call")

        if "tool_response" in call_type:
            payload_text = call.get("output") or call.get("content")
            serialised_payload = _serialise_tool_payload(payload_text)
            if serialised_payload is None:
                continue
            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_identifier,
                    "content": serialised_payload,
                }
            )
            executed = True
            continue

        func_block = call.get("function")
        func_info = dict(func_block) if isinstance(func_block, Mapping) else {}
        name_value = func_info.get("name")
        if not isinstance(name_value, str) or tool_functions is None or name_value not in tool_functions:
            continue
        tool_payload = func_info.get("input")
        if tool_payload is None:
            tool_payload = func_info.get("arguments")

        args: dict[str, Any] = {}
        if isinstance(tool_payload, Mapping):
            args = dict(tool_payload)
        elif isinstance(tool_payload, str):
            raw_text = tool_payload or "{}"
            try:
                parsed: Any = json.loads(raw_text)
                if isinstance(parsed, Mapping):
                    args = dict(parsed)
            except Exception:  # pragma: no cover - defensive
                args = {}

        result = tool_functions[name_value](**args)
        tool_messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_identifier or name_value,
                "content": json.dumps(result),
            }
        )
        executed = True

    return tool_messages, executed


def _file_search_result_text(result: Mapping[str, Any]) -> str:
    """Return the textual content contained in a file-search result."""

    content = result.get("content")
    if isinstance(content, Sequence) and not isinstance(content, (str, bytes)):
        parts: list[str] = []
        for part in content:
            part_map = _to_mapping(part)
            if not part_map:
                continue
            text_value = part_map.get("text")
            if text_value:
                parts.append(str(text_value))
        joined = "\n".join(parts).strip()
        if joined:
            return joined
    text_value = result.get("text")
    if text_value:
        return str(text_value)
    return ""


def _file_search_result_key(result: Mapping[str, Any]) -> FileSearchKey:
    """Return a deduplication key for a file-search result mapping."""

    chunk_id = str(result.get("id") or result.get("chunk_id") or "")
    file_id = str(result.get("file_id") or "")
    text_value = str(result.get("text") or "")
    return chunk_id, file_id, text_value


def _collect_file_search_results(response: Any) -> list[FileSearchResult]:
    """Extract file-search results from a Responses API object."""

    collected: list[FileSearchResult] = []
    seen: set[FileSearchKey] = set()

    for item in getattr(response, "output", []) or []:
        item_dict = _to_mapping(item)
        if not item_dict:
            continue
        content = item_dict.get("content")
        if not isinstance(content, Sequence) or isinstance(content, (str, bytes)):
            continue
        for entry in content:
            entry_dict = _to_mapping(entry)
            if not entry_dict or entry_dict.get("type") != "file_search_results":
                continue
            file_search_block = _to_mapping(entry_dict.get("file_search"))
            if not file_search_block:
                continue
            results = file_search_block.get("results")
            if not isinstance(results, Sequence) or isinstance(results, (str, bytes)):
                continue
            for raw_result in results:
                result_map = _to_mapping(raw_result)
                if not result_map:
                    continue
                normalised = cast(FileSearchResult, dict(result_map))
                metadata = normalised.get("metadata")
                if metadata is not None and not isinstance(metadata, Mapping):
                    metadata_map = _to_mapping(metadata)
                    if metadata_map is not None:
                        normalised["metadata"] = metadata_map
                text_value = _file_search_result_text(normalised)
                if text_value:
                    normalised.setdefault("text", text_value)
                key = _file_search_result_key(normalised)
                if key in seen:
                    continue
                seen.add(key)
                collected.append(normalised)
    return collected


def _record_file_search_results(state: RetryState, response: Any) -> None:
    """Append unique file-search results from ``response`` to ``state``."""

    for entry in _collect_file_search_results(response):
        key = _file_search_result_key(entry)
        if key in state.seen_file_search:
            continue
        state.seen_file_search.add(key)
        state.file_search_results.append(entry)


def _merge_usage_dicts(
    primary_usage: Mapping[str, Any] | None,
    secondary_usage: Mapping[str, Any] | None,
) -> UsageDict:
    """Combine two usage dictionaries by summing numeric values."""

    combined: UsageDict = {}
    for usage in (primary_usage or {}, secondary_usage or {}):
        if not isinstance(usage, Mapping):
            continue
        for key, value in usage.items():
            key_name = str(key)
            combined[key_name] = combined.get(key_name, 0) + _coerce_token_count(value)
    return combined


def _build_comparison_metadata(
    primary: ChatCallResult,
    secondary: ChatCallResult,
    *,
    label: str | None,
    custom: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return structured metadata comparing primary and secondary outputs."""

    metadata: dict[str, Any] = {
        "mode": "dual_prompt",
        "primary": {
            "content": primary.content,
            "usage": dict(primary.usage or {}),
            "tool_calls": list(primary.tool_calls or []),
        },
        "secondary": {
            "content": secondary.content,
            "usage": dict(secondary.usage or {}),
            "tool_calls": list(secondary.tool_calls or []),
        },
    }
    if label:
        metadata["label"] = label

    if primary.content is not None and secondary.content is not None:
        similarity = SequenceMatcher(None, primary.content, secondary.content).ratio()
        metadata["diff"] = {
            "are_equal": primary.content == secondary.content,
            "similarity": similarity,
        }
    else:
        metadata["diff"] = {"are_equal": primary.content == secondary.content}

    if custom:
        metadata["custom"] = dict(custom)

    return metadata


def _convert_tool_choice_to_function_call(choice: Any) -> Any:
    """Translate a Responses tool choice payload to ``function_call``."""

    if choice is None:
        return None
    if isinstance(choice, str):
        lowered = choice.strip().lower()
        if lowered in {"none", "auto"}:
            return lowered
        if lowered:
            return {"name": lowered}
        return None
    if not isinstance(choice, Mapping):
        return None

    choice_type = str(choice.get("type") or "").strip().lower()
    if choice_type and choice_type != "function":
        # Chat Completions only understands ``function`` selectors or the
        # ``auto``/``none`` shorthand.
        if choice_type in {"none", "auto"}:
            return choice_type
        return None

    function_payload = choice.get("function")
    if isinstance(function_payload, Mapping):
        name_value = function_payload.get("name")
        if isinstance(name_value, str) and name_value.strip():
            return {"name": name_value.strip()}

    fallback_name = choice.get("name")
    if isinstance(fallback_name, str) and fallback_name.strip():
        return {"name": fallback_name.strip()}

    return None


def _convert_tools_to_functions(tool_specs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return classic ``functions`` payload derived from ``tool_specs``."""

    functions: list[dict[str, Any]] = []
    for spec in tool_specs:
        if str(spec.get("type") or "").strip().lower() != "function":
            continue
        function_payload: dict[str, Any] = {}
        raw_function = spec.get("function")
        if isinstance(raw_function, Mapping):
            function_payload.update(raw_function)
        for field in ("description", "parameters"):
            if field in spec and field not in function_payload:
                function_payload[field] = spec[field]

        name_value = function_payload.get("name") or spec.get("name")
        if isinstance(name_value, str) and name_value.strip():
            function_payload["name"] = name_value.strip()
        else:
            # Skip unnamed tools; Responses would already have enforced a name.
            continue

        functions.append(function_payload)
    return functions


@dataclass(frozen=True)
class PayloadContext:
    """Normalized inputs for building chat or Responses payloads."""

    messages: list[dict[str, Any]]
    model: str | None
    temperature: float | None
    max_completion_tokens: int | None
    candidate_models: list[str]
    tool_specs: list[dict[str, Any]]
    tool_functions: Mapping[str, Callable[..., Any]]
    tool_choice: Any | None
    schema_bundle: SchemaFormatBundle | None
    reasoning_effort: str | None
    extra: dict[str, Any] | None
    router_estimate: PromptCostEstimate | None
    previous_response_id: str | None
    force_classic_for_tools: bool
    api_mode_override: str | None = None

    @property
    def use_classic_api(self) -> bool:
        return app_config.USE_CLASSIC_API or self.force_classic_for_tools


@dataclass
class _BasePayloadBuilder:
    context: PayloadContext

    def _wrap(self, payload: dict[str, Any]) -> ResponsesRequest:
        return ResponsesRequest(
            payload=payload,
            model=self.context.model,
            tool_specs=self.context.tool_specs,
            tool_functions=self.context.tool_functions,
            candidate_models=self.context.candidate_models,
            api_mode_override=self.context.api_mode_override,
        )


class ChatPayloadBuilder(_BasePayloadBuilder):
    """Build Chat Completions payloads from a :class:`PayloadContext`."""

    def build(self) -> ResponsesRequest:
        payload: dict[str, Any] = {"model": self.context.model, "messages": self.context.messages}
        if self.context.temperature is not None and model_supports_temperature(self.context.model):  # TEMP_SUPPORTED
            payload["temperature"] = self.context.temperature
        if self.context.max_completion_tokens is not None:
            payload["max_completion_tokens"] = self.context.max_completion_tokens
        if self.context.schema_bundle is not None:
            payload["response_format"] = deepcopy(self.context.schema_bundle.chat_response_format)
        if self.context.tool_specs:
            functions = _convert_tools_to_functions(self.context.tool_specs)
            if functions:
                payload["functions"] = functions
                function_call = _convert_tool_choice_to_function_call(self.context.tool_choice)
                if function_call is not None:
                    payload["function_call"] = function_call

        return self._wrap(payload)


class ResponsesPayloadBuilder(_BasePayloadBuilder):
    """Build Responses API payloads from a :class:`PayloadContext`."""

    def build(self) -> ResponsesRequest:
        payload: dict[str, Any] = {
            "model": self.context.model,
            "input": self.context.messages,
        }
        if self.context.previous_response_id:
            payload["previous_response_id"] = self.context.previous_response_id
        if self.context.temperature is not None and model_supports_temperature(self.context.model):  # TEMP_SUPPORTED
            payload["temperature"] = self.context.temperature
        if model_supports_reasoning(self.context.model):
            payload["reasoning"] = {"effort": self.context.reasoning_effort}
        if self.context.max_completion_tokens is not None:
            payload["max_output_tokens"] = self.context.max_completion_tokens
        if self.context.schema_bundle is not None:
            text_config: dict[str, Any] = dict(payload.get("text") or {})
            text_config.pop("type", None)
            text_config["format"] = deepcopy(self.context.schema_bundle.responses_format)
            payload["text"] = text_config
        if self.context.extra:
            payload.update(self.context.extra)
        if self.context.router_estimate is not None:
            metadata: dict[str, Any] = dict(payload.get("metadata") or {})
            router_info: dict[str, Any] = dict(metadata.get("router") or {})
            router_info.update(
                {
                    "complexity": self.context.router_estimate.complexity.value,
                    "tokens": self.context.router_estimate.total_tokens,
                    "hard_words": self.context.router_estimate.hard_word_count,
                }
            )
            metadata["router"] = router_info
            payload["metadata"] = metadata

        return self._wrap(payload)


def _prepare_payload(
    messages: Sequence[dict],
    *,
    model: Optional[str],
    temperature: float | None,
    max_completion_tokens: int | None,
    json_schema: Optional[dict],
    tools: Optional[list],
    tool_choice: Optional[Any],
    tool_functions: Optional[Mapping[str, Callable[..., Any]]],
    reasoning_effort: Optional[str],
    extra: Optional[dict],
    include_analysis_tools: bool = True,
    task: ModelTask | str | None = None,
    previous_response_id: str | None = None,
) -> ResponsesRequest:
    """Assemble the payload for the configured OpenAI API."""

    selected_task = task or ModelTask.DEFAULT
    router_estimate: PromptCostEstimate | None = None
    candidate_override = model
    if model is None:
        base_model = select_model(selected_task)
        chosen_model, router_estimate = route_model_for_messages(messages, default_model=base_model)
        if chosen_model != base_model:
            candidate_override = chosen_model
            model = get_first_available_model(selected_task, override=chosen_model)
        else:
            model = base_model
    if reasoning_effort is None:
        reasoning_effort = st.session_state.get(StateKeys.REASONING_EFFORT, REASONING_EFFORT)

    candidate_models = get_model_candidates(selected_task, override=candidate_override)
    if model and model not in candidate_models:
        candidate_models = [model, *candidate_models]
    elif not candidate_models and model:
        candidate_models = [model]

    def _normalise_tool_spec(spec: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
        """Return a copy of ``spec`` normalised to the Responses API schema."""

        prepared = dict(spec)
        raw_function_payload = prepared.get("function")
        function_payload = raw_function_payload if isinstance(raw_function_payload, Mapping) else None
        tool_type = prepared.get("type")
        has_function_payload = function_payload is not None
        has_parameters = "parameters" in prepared or (function_payload is not None and "parameters" in function_payload)
        is_function_tool = bool(tool_type == "function" or has_function_payload or has_parameters)

        if not is_function_tool:
            name_value = prepared.get("name")
            if isinstance(name_value, str) and name_value.strip():
                prepared["name"] = name_value.strip()
                has_name = True
            else:
                fallback = tool_type.strip() if isinstance(tool_type, str) else ""
                if fallback:
                    prepared["name"] = fallback
                    has_name = True
                else:
                    has_name = False
            return prepared, has_name

        function_dict = dict(function_payload) if function_payload is not None else {}
        top_level_name = prepared.get("name")

        for field in ("description", "parameters"):
            if field in prepared and field not in function_dict:
                function_dict[field] = prepared[field]
            prepared.pop(field, None)

        function_name = function_dict.get("name")
        if not (isinstance(function_name, str) and function_name.strip()):
            if isinstance(top_level_name, str) and top_level_name.strip():
                function_dict["name"] = top_level_name.strip()
                function_name = function_dict["name"]
            else:
                function_name = None
        else:
            function_name = function_name.strip()

        if function_name:
            function_dict["name"] = function_name
            prepared["name"] = function_name
            has_name = True
        else:
            prepared.pop("name", None)
            has_name = False

        prepared["type"] = "function"
        prepared["function"] = function_dict
        return prepared, has_name

    def _normalise_tool_choice_spec(choice: Any) -> Any:
        """Translate legacy function ``tool_choice`` payloads to the new schema."""

        if not isinstance(choice, Mapping):
            return choice

        normalised = dict(choice)
        if normalised.get("type") != "function":
            return normalised

        merged_function: dict[str, Any] = {}
        existing_function = normalised.get("function")
        if isinstance(existing_function, Mapping):
            merged_function.update(existing_function)

        sentinel = object()
        for field in ("name", "arguments", "reasoning"):
            value = normalised.pop(field, sentinel)
            if value is sentinel:
                continue
            if field not in merged_function:
                merged_function[field] = value

        if merged_function:
            normalised["function"] = merged_function
        else:
            normalised.pop("function", None)

        return normalised

    raw_tools = [dict(tool) for tool in (tools or [])]
    tool_map = dict(tool_functions or {})
    requested_tools = bool(raw_tools or tool_map)
    analysis_tools_enabled = include_analysis_tools and (
        app_config.USE_CLASSIC_API or requested_tools or app_config.RESPONSES_ALLOW_TOOLS
    )
    if analysis_tools_enabled:
        from core import analysis_tools

        base_tools, base_funcs = analysis_tools.build_analysis_tools()
        raw_tools.extend(dict(tool) for tool in base_tools)
        tool_map = {**base_funcs, **tool_map}

    converted_tools: list[dict[str, Any]] = []
    missing_name_indices: list[int] = []
    used_names: set[str] = set()

    for index, tool in enumerate(raw_tools):
        converted, has_name = _normalise_tool_spec(tool)
        if converted.get("type") == "function":
            function_block = converted.get("function", {})
            name_value = function_block.get("name")
            if isinstance(name_value, str) and name_value.strip():
                used_names.add(name_value)
            elif not has_name:
                missing_name_indices.append(index)
        converted_tools.append(converted)

    available_names = [name for name in tool_map if name not in used_names]
    for index in missing_name_indices:
        function_block = converted_tools[index].setdefault("function", {})
        fallback_name: str | None = None
        if available_names:
            fallback_name = available_names.pop(0)
        elif function_block.get("parameters"):
            fallback_name = f"function_{index}"

        if not fallback_name:
            raise ValueError("Function tools must define a 'name'.")

        function_block["name"] = fallback_name
        converted_tools[index]["name"] = fallback_name
        used_names.add(fallback_name)

    combined_tools = converted_tools

    messages_payload = [dict(message) for message in messages]
    normalised_tool_choice = _normalise_tool_choice_spec(tool_choice) if tool_choice is not None else None

    schema_bundle: SchemaFormatBundle | None = None
    if json_schema is not None:
        schema_bundle = build_schema_format_bundle(json_schema)

    force_classic_for_tools = bool(
        combined_tools and not (app_config.USE_CLASSIC_API or app_config.RESPONSES_ALLOW_TOOLS)
    )
    api_mode_override: str | None = "chat" if force_classic_for_tools and not app_config.USE_CLASSIC_API else None

    context = PayloadContext(
        messages=messages_payload,
        model=model,
        temperature=temperature,
        max_completion_tokens=max_completion_tokens,
        candidate_models=candidate_models,
        tool_specs=combined_tools,
        tool_functions=tool_map,
        tool_choice=normalised_tool_choice,
        schema_bundle=schema_bundle,
        reasoning_effort=reasoning_effort,
        extra=extra,
        router_estimate=router_estimate,
        previous_response_id=previous_response_id,
        force_classic_for_tools=force_classic_for_tools,
        api_mode_override=api_mode_override,
    )

    builder: _BasePayloadBuilder
    if context.use_classic_api:
        builder = ChatPayloadBuilder(context)
    else:
        builder = ResponsesPayloadBuilder(context)

    return builder.build()


@dataclass
class ChatCallResult:
    """Unified return type for :func:`call_chat_api`.

    Attributes:
        content: Text content returned by the model, if any.
        tool_calls: List of tool call payloads.
        usage: Token usage information.
        response_id: Identifier assigned by the OpenAI API, when available.
    """

    content: Optional[str]
    tool_calls: list[ToolCallPayload]
    usage: UsageDict
    response_id: str | None = None
    raw_response: Any | None = None
    file_search_results: Optional[list[FileSearchResult]] = None
    secondary_content: Optional[str] = None
    secondary_tool_calls: Optional[list[ToolCallPayload]] = None
    secondary_usage: Optional[UsageDict] = None
    comparison: Optional[Mapping[str, Any]] = None
    secondary_raw_response: Any | None = None
    secondary_file_search_results: Optional[list[FileSearchResult]] = None
    secondary_response_id: str | None = None


ComparisonBuilder = Callable[["ChatCallResult", "ChatCallResult"], Mapping[str, Any]]


class ChatStream(Iterable[str]):
    """Iterator over streaming chat responses."""

    def __init__(self, payload: Dict[str, Any], model: str, *, task: ModelTask | str | None):
        prepared_payload = dict(payload)
        prepared_payload.setdefault("timeout", OPENAI_REQUEST_TIMEOUT)
        self._payload = prepared_payload
        self._model = model
        self._task = task
        self._result: ChatCallResult | None = None
        self._buffer: list[str] = []

    def __iter__(self) -> Iterator[str]:
        yield from self._consume()

    def _consume(self) -> Iterator[str]:
        client = get_client()
        final_response: Any | None = None
        missing_completion_event = False
        try:
            if app_config.USE_CLASSIC_API:
                with client.chat.completions.stream(**self._payload) as stream:
                    for chat_event in stream:
                        for chunk in _stream_event_chunks(chat_event):
                            if chunk:
                                self._buffer.append(chunk)
                                yield chunk
                    final_response = stream.get_final_completion()
            else:
                with client.responses.stream(**self._payload) as stream:
                    for responses_event in stream:
                        for chunk in _stream_event_chunks(responses_event):
                            if chunk:
                                self._buffer.append(chunk)
                                yield chunk
                    try:
                        final_response = stream.get_final_response()
                        if final_response is None:
                            missing_completion_event = True
                            logger.warning(
                                "Responses stream returned no final payload; retrying without streaming.",
                            )
                    except RuntimeError as error:
                        if _is_missing_completion_event_error(error):
                            missing_completion_event = True
                            logger.warning(
                                "Responses stream missing completion event; retrying without streaming.",
                                exc_info=error,
                            )
                        else:
                            raise
        except (OpenAIError, RuntimeError) as error:
            if _is_missing_completion_event_error(error) or missing_completion_event:
                logger.warning("Streaming failure detected; attempting fallback via API retries.", exc_info=error)
                recovered = self._recover_stream_response(client)
                if recovered is not None:
                    final_response = recovered
                elif self._buffer:
                    logger.warning(
                        "Streaming finished without completion event; finalising buffered text.",
                        exc_info=error,
                    )
                    self._finalise_partial()
                    return
                else:
                    _handle_streaming_error(error)
                    return
            else:
                _handle_streaming_error(error)
                return
        else:
            if final_response is None and missing_completion_event:
                final_response = self._recover_stream_response(client)
                if final_response is None and self._buffer:
                    logger.warning(
                        "Streaming ended without completion event; using buffered text as final output.",
                    )
                    self._finalise_partial()
                    return

        if final_response is None:
            self._finalise_partial()
        else:
            self._finalise(final_response)

    def _recover_stream_response(self, client: OpenAI) -> Any | None:
        """Return a non-streamed payload to finalise the request if possible."""

        if app_config.USE_CLASSIC_API:
            return None

        response = self._retry_responses_without_stream(client)
        if response is not None:
            return response

        return self._retry_chat_completion(client)

    def _retry_responses_without_stream(self, client: OpenAI) -> Any | None:
        """Retry the original Responses payload without streaming."""

        payload = dict(self._payload)
        payload.pop("stream", None)
        try:
            logger.info("Retrying Responses request without streaming after missing completion event.")
            return client.responses.create(**payload)
        except OpenAIError as error:
            logger.warning("Responses retry failed; will attempt Chat Completions fallback.", exc_info=error)
        except Exception as error:  # pragma: no cover - defensive
            logger.error("Unexpected error during Responses retry.", exc_info=error)
        return None

    def _retry_chat_completion(self, client: OpenAI) -> Any | None:
        """Fallback to the Chat Completions API when Responses streaming fails."""

        chat_client = getattr(client, "chat", None)
        completions = getattr(chat_client, "completions", None)
        if completions is None:
            return None

        fallback_payload = _convert_responses_payload_to_chat(self._payload)
        if fallback_payload is None:
            return None

        try:
            logger.info("Falling back to Chat Completions request after Responses streaming failure.")
            return completions.create(**fallback_payload)
        except OpenAIError as error:
            logger.error("Chat Completions fallback failed.", exc_info=error)
        except Exception as error:  # pragma: no cover - defensive
            logger.error("Unexpected Chat fallback failure.", exc_info=error)
        return None

    def _finalise(self, response: Any) -> None:
        tool_calls = _collect_tool_calls(response)
        if tool_calls:
            raise RuntimeError(
                "Streaming responses requested tool execution. Use call_chat_api for tool-enabled prompts."
            )
        content = _extract_output_text(response)
        usage_block = _normalise_usage(_extract_usage_block(response) or {})
        usage = _numeric_usage(usage_block)
        _update_usage_counters(usage, task=self._task)
        response_id = _extract_response_id(response)
        self._result = ChatCallResult(
            content,
            tool_calls,
            usage,
            response_id=response_id,
        )

    def _finalise_partial(self) -> None:
        """Persist streaming output when the final event is missing."""

        partial_text = self.text
        empty_usage: UsageDict = {}
        self._result = ChatCallResult(partial_text if partial_text else None, [], empty_usage, response_id=None)

    @property
    def result(self) -> ChatCallResult:
        """Return the final :class:`ChatCallResult` once streaming finished."""

        if self._result is None:
            raise RuntimeError("Stream not fully consumed yet")
        return self._result

    @property
    def text(self) -> str:
        """Return the concatenated streamed text observed so far."""

        return "".join(self._buffer)


def _stream_event_chunks(event: Any) -> Iterable[str]:
    """Yield textual deltas contained in a streaming event."""

    data = _to_mapping(event)
    if not data:
        return []

    typ = str(data.get("type") or "")
    if "error" in typ or typ.endswith(".failed"):
        error_info = data.get("error") or {}
        message = error_info.get("message") or str(error_info or event)
        raise RuntimeError(f"OpenAI streaming error: {message}")

    if typ.endswith(".delta"):
        delta_value = data.get("delta")
        if isinstance(delta_value, str):
            return [delta_value]
        if isinstance(delta_value, Sequence) and not isinstance(delta_value, (str, bytes)):
            chunks: list[str] = []
            for part in delta_value:
                part_map = _to_mapping(part)
                if not part_map:
                    continue
                text_value = part_map.get("text")
                if isinstance(text_value, str):
                    chunks.append(text_value)
            if chunks:
                return chunks
        text_value = data.get("text")
        if isinstance(text_value, str):
            return [text_value]

    if typ.endswith(".added"):
        item = data.get("item")
        if item is not None:
            mapping = _to_mapping(item)
        else:
            mapping = None
        if mapping:
            content = mapping.get("content")
            if isinstance(content, Sequence) and not isinstance(content, (str, bytes)):
                added_chunks: list[str] = []
                for part in content:
                    part_map = _to_mapping(part)
                    if not part_map:
                        continue
                    text_value = part_map.get("text")
                    if isinstance(text_value, str):
                        added_chunks.append(text_value)
                if added_chunks:
                    return added_chunks

    return []


def _is_missing_completion_event_error(error: BaseException | None) -> bool:
    """Return ``True`` when ``error`` indicates a missing completion event."""

    if not error:
        return False
    message = str(error)
    if not message:
        return False
    lowered = message.lower()
    return "response.completed" in lowered or "completion event" in lowered


def _convert_responses_payload_to_chat(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    """Translate a Responses payload to a Chat Completions payload when possible."""

    raw_messages = payload.get("input")
    if not isinstance(raw_messages, Sequence):
        return None

    messages: list[dict[str, Any]] = []
    for message in raw_messages:
        if isinstance(message, Mapping):
            messages.append(dict(message))
        else:
            messages.append({})

    chat_payload: dict[str, Any] = {
        "model": payload.get("model"),
        "messages": messages,
        "timeout": payload.get("timeout", OPENAI_REQUEST_TIMEOUT),
    }

    temperature = payload.get("temperature")
    if temperature is not None and model_supports_temperature(payload.get("model")):
        chat_payload["temperature"] = temperature

    max_tokens = payload.get("max_output_tokens")
    if max_tokens is not None:
        chat_payload["max_completion_tokens"] = max_tokens

    text_block = payload.get("text")
    if isinstance(text_block, Mapping):
        format_block = text_block.get("format")
        if isinstance(format_block, Mapping) and format_block.get("type") == "json_schema":
            schema_name: str | None = None
            schema_body: Mapping[str, Any] | None = None
            strict_value: bool | None = None

            json_schema_block = format_block.get("json_schema")
            if isinstance(json_schema_block, Mapping):
                if isinstance(json_schema_block.get("name"), str) and json_schema_block["name"].strip():
                    schema_name = json_schema_block["name"].strip()
                schema_candidate = json_schema_block.get("schema")
                if isinstance(schema_candidate, Mapping):
                    schema_body = schema_candidate
                if "strict" in json_schema_block:
                    strict_value = bool(json_schema_block.get("strict"))

            if (not schema_name or not schema_body) and isinstance(format_block.get("name"), str):
                name_candidate = format_block["name"].strip()
                if name_candidate:
                    schema_name = schema_name or name_candidate
            if schema_body is None:
                schema_candidate = format_block.get("schema")
                if isinstance(schema_candidate, Mapping):
                    schema_body = schema_candidate
            if strict_value is None and "strict" in format_block:
                strict_value = bool(format_block.get("strict"))

            if schema_name and schema_body:
                json_schema_payload: dict[str, Any] = {
                    "name": schema_name,
                    "schema": dict(schema_body),
                }
                if strict_value is not None:
                    json_schema_payload["strict"] = strict_value
                schema_bundle = build_schema_format_bundle(json_schema_payload)
                chat_payload["response_format"] = deepcopy(schema_bundle.chat_response_format)

    return chat_payload


def get_client() -> OpenAI:
    """Return a configured OpenAI client."""

    global client
    if client is None:
        key = OPENAI_API_KEY
        if not key:
            _show_missing_api_key_alert()
            raise RuntimeError(resolve_message(_MISSING_API_KEY_RUNTIME_MESSAGE))
        base = OPENAI_BASE_URL or None
        init_kwargs: dict[str, Any] = {
            "api_key": key,
            "base_url": base,
            "timeout": OPENAI_REQUEST_TIMEOUT,
        }
        organisation = OPENAI_ORGANIZATION.strip() if isinstance(OPENAI_ORGANIZATION, str) else OPENAI_ORGANIZATION
        if organisation:
            init_kwargs["organization"] = organisation
        project = OPENAI_PROJECT.strip() if isinstance(OPENAI_PROJECT, str) else OPENAI_PROJECT
        if project:
            init_kwargs["project"] = project
        client = OpenAI(**init_kwargs)
    return client


def _show_missing_api_key_alert() -> None:
    """Display a user-facing hint about missing API credentials once per session."""

    try:
        if st.session_state.get(_MISSING_API_KEY_ALERT_STATE_KEY):
            return
    except Exception:  # pragma: no cover - defensive when Streamlit isn't initialised
        pass

    emitted = False
    for emitter in (display_error, getattr(st, "error", None)):
        if emitter is None:
            continue
        try:
            emitter(resolve_message(_MISSING_API_KEY_ALERT_MESSAGE))
            emitted = True
            break
        except Exception:  # noqa: BLE001 - fall back to next emitter
            continue

    if not emitted:
        return

    try:
        st.session_state[_MISSING_API_KEY_ALERT_STATE_KEY] = True
    except Exception:  # pragma: no cover - Streamlit session state unavailable
        pass


def _describe_openai_error(error: OpenAIError) -> tuple[str, str]:
    """Return the user-facing and log messages for an OpenAI error."""

    if isinstance(error, AuthenticationError):
        detail = getattr(error, "message", str(error))
        return (
            resolve_message(_AUTHENTICATION_ERROR_MESSAGE),
            f"OpenAI authentication error: {detail}",
        )

    if isinstance(error, RateLimitError):
        detail = getattr(error, "message", str(error))
        return (
            resolve_message(_RATE_LIMIT_ERROR_MESSAGE),
            f"OpenAI rate limit error: {detail}",
        )

    if isinstance(error, (APIConnectionError, APITimeoutError)):
        detail = getattr(error, "message", str(error))
        return (
            resolve_message(_NETWORK_ERROR_MESSAGE),
            f"OpenAI network error: {detail}",
        )

    if isinstance(error, BadRequestError) or getattr(error, "type", "") == "invalid_request_error":
        detail = getattr(error, "message", str(error))
        log_msg = f"OpenAI invalid request: {detail}"
        return resolve_message(_INVALID_REQUEST_ERROR_MESSAGE), log_msg

    if isinstance(error, APIError):
        detail = getattr(error, "message", str(error))
        user_msg = resolve_message((f"OpenAI-API-Fehler: {detail}", f"OpenAI API error: {detail}"))
        return user_msg, f"OpenAI API error: {detail}"

    fallback = str(error)
    user_msg = resolve_message((f"Unerwarteter OpenAI-Fehler: {fallback}", f"Unexpected OpenAI error: {fallback}"))
    return user_msg, f"Unexpected OpenAI error: {fallback}"


def _handle_openai_error(error: OpenAIError) -> None:
    """Raise a user-friendly ``RuntimeError`` for OpenAI failures."""

    user_msg, log_msg = _describe_openai_error(error)
    logger.error(log_msg, exc_info=error)
    try:  # pragma: no cover - Streamlit may not be initialised in tests
        st.error(user_msg)
    except Exception:  # noqa: BLE001
        pass
    raise RuntimeError(user_msg) from error


def _handle_streaming_error(error: Exception) -> None:
    """Surface streaming failures with user-facing feedback before re-raising."""

    if isinstance(error, OpenAIError):
        _handle_openai_error(error)
        return

    message = str(error)
    lowered = message.lower()

    if "rate limit" in lowered or "429" in lowered or "too many requests" in lowered:
        user_msg = resolve_message(_RATE_LIMIT_ERROR_MESSAGE)
        log_msg = f"OpenAI streaming rate limit: {message}"
    elif any(keyword in lowered for keyword in ("timeout", "timed out", "connection", "network", "dns", "503", "504")):
        user_msg = resolve_message(_NETWORK_ERROR_MESSAGE)
        log_msg = f"OpenAI streaming network error: {message}"
    elif any(
        keyword in lowered
        for keyword in ("invalid", "bad request", "prompt", "context length", "length limit", "unsupported")
    ):
        user_msg = resolve_message(_INVALID_REQUEST_ERROR_MESSAGE)
        log_msg = f"OpenAI streaming invalid request: {message}"
    else:
        user_msg = resolve_message((f"Unerwarteter OpenAI-Fehler: {message}", f"Unexpected OpenAI error: {message}"))
        log_msg = user_msg

    logger.error(log_msg, exc_info=error)
    try:  # pragma: no cover - Streamlit may not be initialised in tests
        st.error(user_msg)
    except Exception:  # noqa: BLE001
        pass
    raise RuntimeError(user_msg) from error


def _on_api_giveup(details: Any) -> None:
    """Handle a final API error after retries have been exhausted."""

    err = details.get("exception")
    if isinstance(err, BadRequestError):
        raise err
    if isinstance(err, OpenAIError):  # pragma: no cover - defensive
        _handle_openai_error(err)
    raise err  # pragma: no cover - re-raise unexpected errors


def _call_chat_api_single(
    messages: Sequence[dict],
    *,
    model: str | None = None,
    temperature: float | None = 0.2,
    max_completion_tokens: int | None = None,
    json_schema: Optional[dict] = None,
    tools: Optional[list] = None,
    tool_choice: Optional[Any] = None,
    tool_functions: Optional[Mapping[str, Callable[..., Any]]] = None,
    reasoning_effort: str | None = None,
    verbosity: str | None = None,
    extra: Optional[dict] = None,
    task: ModelTask | str | None = None,
    include_raw_response: bool = False,
    capture_file_search: bool = False,
    previous_response_id: str | None = None,
) -> ChatCallResult:
    """Execute a single chat completion call with optional tool handling."""

    messages_with_hint = _inject_verbosity_hint(messages, _resolve_verbosity(verbosity))

    request = _prepare_payload(
        messages_with_hint,
        model=model,
        temperature=temperature,
        max_completion_tokens=max_completion_tokens,
        json_schema=json_schema,
        tools=tools,
        tool_choice=tool_choice,
        tool_functions=tool_functions,
        reasoning_effort=reasoning_effort,
        extra=extra,
        task=task,
        previous_response_id=previous_response_id,
    )

    payload = dict(request.payload)
    api_mode_override = request.api_mode_override

    message_key = "messages" if "messages" in payload else "input"
    base_messages = payload.get(message_key)
    if isinstance(base_messages, list):
        messages_list = base_messages
    else:
        messages_list = list(messages_with_hint)
        payload[message_key] = messages_list

    context = build_fallback_context(request.model, request.candidate_models)
    current_model = context.initial_model()
    payload["model"] = current_model

    retry_state = create_retry_state()

    while True:
        try:
            response = _execute_response(payload, current_model, api_mode=api_mode_override)
        except OpenAIError as err:
            if is_model_available(current_model):
                raise

            next_model = context.register_failure(current_model)

            if next_model is None:
                raise

            logger.warning(
                "Model '%s' unavailable (%s); retrying with fallback '%s'.",
                current_model,
                getattr(err, "message", str(err)),
                next_model,
            )
            payload["model"] = next_model
            current_model = next_model
            continue

        response_id = _extract_response_id(response)
        if response_id and not app_config.USE_CLASSIC_API and api_mode_override != "chat":
            payload["previous_response_id"] = response_id

        content = _extract_output_text(response)

        tool_calls = _collect_tool_calls(response)

        usage_block = _normalise_usage(_extract_usage_block(response) or {})
        numeric_usage = _numeric_usage(usage_block)
        _accumulate_usage(retry_state, numeric_usage)

        if capture_file_search:
            _record_file_search_results(retry_state, response)

        if tool_calls:
            retry_state.last_tool_calls = tool_calls

        if not tool_calls:
            merged_usage = _usage_snapshot(retry_state, numeric_usage)
            _update_usage_counters(merged_usage, task=task)
            result_tool_calls = retry_state.last_tool_calls
            return ChatCallResult(
                content,
                result_tool_calls,
                merged_usage,
                response_id=response_id,
                raw_response=response if include_raw_response else None,
                file_search_results=retry_state.file_search_results or None,
            )

        tool_messages, executed = _execute_tool_invocations(
            tool_calls,
            tool_functions=request.tool_functions,
        )
        if tool_messages:
            messages_list.extend(tool_messages)
            payload[message_key] = messages_list

        if not executed:
            merged_usage = _usage_snapshot(retry_state, numeric_usage)
            _update_usage_counters(merged_usage, task=task)
            result_tool_calls = tool_calls or retry_state.last_tool_calls
            return ChatCallResult(
                content,
                result_tool_calls,
                merged_usage,
                response_id=response_id,
                raw_response=response if include_raw_response else None,
                file_search_results=retry_state.file_search_results or None,
            )


@retry_with_backoff(
    giveup=lambda exc: isinstance(exc, BadRequestError) or is_unrecoverable_schema_error(exc),
    on_giveup=_on_api_giveup,
)
def call_chat_api(
    messages: Sequence[dict],
    *,
    model: str | None = None,
    temperature: float | None = 0.2,
    max_completion_tokens: int | None = None,
    json_schema: Optional[dict] = None,
    tools: Optional[list] = None,
    tool_choice: Optional[Any] = None,
    tool_functions: Optional[Mapping[str, Callable[..., Any]]] = None,
    reasoning_effort: str | None = None,
    verbosity: str | None = None,
    extra: Optional[dict] = None,
    task: ModelTask | str | None = None,
    include_raw_response: bool = False,
    capture_file_search: bool = False,
    previous_response_id: str | None = None,
    comparison_messages: Sequence[dict] | None = None,
    comparison_options: Optional[Mapping[str, Any]] = None,
    comparison_label: str | None = None,
) -> ChatCallResult:
    """Call the OpenAI chat endpoint and return a :class:`ChatCallResult`.

    The function automatically targets either the Responses API or the classic
    Chat Completions API depending on configuration. When
    ``comparison_messages`` are supplied a second request is dispatched in
    parallel (unless ``comparison_options['dispatch']`` is set to
    ``"sequential"``). Both responses are returned along with basic similarity
    metadata so callers can decide which variant to keep.
    """

    if _llm_disabled():
        _show_missing_api_key_alert()
        raise RuntimeError(llm_disabled_message())

    single_kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "max_completion_tokens": max_completion_tokens,
        "json_schema": json_schema,
        "tools": tools,
        "tool_choice": tool_choice,
        "tool_functions": tool_functions,
        "reasoning_effort": reasoning_effort,
        "verbosity": verbosity,
        "extra": extra,
        "task": task,
        "include_raw_response": include_raw_response,
        "capture_file_search": capture_file_search,
        "previous_response_id": previous_response_id,
    }

    if comparison_messages is None:
        return _call_chat_api_single(messages, **single_kwargs)

    options = dict(comparison_options or {})
    dispatch = str(options.pop("dispatch", "parallel")).lower()
    if dispatch not in {"parallel", "sequential"}:
        raise ValueError("comparison_options['dispatch'] must be 'parallel' or 'sequential'")

    metadata_builder: ComparisonBuilder | None = options.pop("metadata_builder", None)
    if metadata_builder is not None and not callable(metadata_builder):
        raise TypeError("comparison_options['metadata_builder'] must be callable")

    label_override = options.pop("label", None)
    if label_override is not None:
        comparison_label = label_override

    allowed_override_keys = {
        "model",
        "temperature",
        "max_completion_tokens",
        "json_schema",
        "tools",
        "tool_choice",
        "tool_functions",
        "reasoning_effort",
        "verbosity",
        "extra",
        "task",
        "previous_response_id",
    }

    secondary_kwargs = dict(single_kwargs)
    for key in list(options):
        if key in allowed_override_keys:
            secondary_kwargs[key] = options.pop(key)

    if options:
        remaining = ", ".join(sorted(options.keys()))
        raise ValueError(f"Unsupported comparison_options keys: {remaining}")

    if dispatch == "parallel":
        with ThreadPoolExecutor(max_workers=2) as executor:
            primary_future = executor.submit(_call_chat_api_single, messages, **single_kwargs)
            secondary_future = executor.submit(
                _call_chat_api_single,
                comparison_messages,
                **secondary_kwargs,
            )
            primary_result = primary_future.result()
            secondary_result = secondary_future.result()
    else:
        primary_result = _call_chat_api_single(messages, **single_kwargs)
        secondary_result = _call_chat_api_single(comparison_messages, **secondary_kwargs)

    combined_usage = _merge_usage_dicts(primary_result.usage, secondary_result.usage)

    custom_metadata: Mapping[str, Any] | None = None
    if metadata_builder is not None:
        try:
            built = metadata_builder(primary_result, secondary_result)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Custom comparison metadata builder failed: %s", exc, exc_info=exc)
        else:
            if built is not None:
                if isinstance(built, Mapping):
                    custom_metadata = dict(built)
                else:
                    custom_metadata = {"value": built}

    comparison = _build_comparison_metadata(
        primary_result,
        secondary_result,
        label=comparison_label,
        custom=custom_metadata,
    )

    return ChatCallResult(
        content=primary_result.content,
        tool_calls=list(primary_result.tool_calls),
        usage=combined_usage,
        response_id=primary_result.response_id,
        secondary_content=secondary_result.content,
        secondary_tool_calls=list(secondary_result.tool_calls),
        secondary_usage=cast(UsageDict, dict(secondary_result.usage)),
        comparison=comparison,
        raw_response=primary_result.raw_response,
        file_search_results=primary_result.file_search_results,
        secondary_raw_response=secondary_result.raw_response,
        secondary_file_search_results=secondary_result.file_search_results,
        secondary_response_id=secondary_result.response_id,
    )


def stream_chat_api(
    messages: Sequence[dict],
    *,
    model: str | None = None,
    temperature: float | None = 0.2,
    max_completion_tokens: int | None = None,
    json_schema: Optional[dict] = None,
    reasoning_effort: str | None = None,
    verbosity: str | None = None,
    extra: Optional[dict] = None,
    task: ModelTask | str | None = None,
) -> ChatStream:
    """Return a :class:`ChatStream` yielding incremental text deltas.

    Streaming currently supports plain text generations without tool execution.
    ``tools``/``tool_functions`` are intentionally not accepted to avoid
    partially-executed tool calls.
    """

    if _llm_disabled():
        _show_missing_api_key_alert()
        raise RuntimeError(llm_disabled_message())

    messages_with_hint = _inject_verbosity_hint(messages, _resolve_verbosity(verbosity))

    request = _prepare_payload(
        messages_with_hint,
        model=model,
        temperature=temperature,
        max_completion_tokens=max_completion_tokens,
        json_schema=json_schema,
        tools=None,
        tool_choice=None,
        tool_functions=None,
        reasoning_effort=reasoning_effort,
        extra=extra,
        include_analysis_tools=False,
        task=task,
    )

    if request.tool_specs or request.tool_functions:
        raise ValueError("Streaming responses do not support tool execution.")

    if not request.model:
        raise RuntimeError("No model resolved for streaming request")

    return ChatStream(request.payload, request.model, task=task)


def _chat_content(res: Any) -> str:
    """Return the textual content from a chat API result."""

    if hasattr(res, "content"):
        return getattr(res, "content") or ""
    if isinstance(res, str):
        return res
    if isinstance(res, dict):
        if isinstance(res.get("content"), str):
            return res["content"]
        try:
            choices = res.get("choices", [])
            if choices:
                msg = choices[0].get("message", {})
                if isinstance(msg.get("content"), str):
                    return msg["content"] or ""
        except Exception:
            pass
    return ""


__all__ = [
    "ChatCallResult",
    "call_chat_api",
    "stream_chat_api",
    "ChatStream",
    "get_client",
    "client",
    "model_supports_reasoning",
    "model_supports_temperature",
    "_chat_content",
    "build_need_analysis_json_schema_payload",
    "SchemaFormatBundle",
    "build_schema_format_bundle",
    "is_unrecoverable_schema_error",
]
