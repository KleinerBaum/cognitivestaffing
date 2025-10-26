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
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from difflib import SequenceMatcher
from threading import Lock
from typing import Any, Callable, Dict, Iterable, Iterator, Mapping, Optional, Sequence, Tuple

import backoff
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

from config import (
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_ORGANIZATION,
    OPENAI_PROJECT,
    OPENAI_REQUEST_TIMEOUT,
    USE_CLASSIC_API,
    REASONING_EFFORT,
    STRICT_JSON,
    VERBOSITY,
    ModelTask,
    get_active_verbosity,
    get_first_available_model,
    get_model_candidates,
    get_model_for,
    is_model_available,
    mark_model_unavailable,
    normalise_verbosity,
)
from constants.keys import StateKeys
from llm.cost_router import route_model_for_messages
from utils.errors import display_error

logger = logging.getLogger("cognitive_needs.openai")
tracer = trace.get_tracer(__name__)

# Global client instance (monkeypatchable in tests)
client: OpenAI | None = None


_REASONING_MODEL_PATTERN = re.compile(r"^o\d")
_MODELS_WITHOUT_TEMPERATURE: set[str] = set()
_MODELS_WITHOUT_REASONING: set[str] = set()
_USAGE_LOCK = Lock()


_MISSING_API_KEY_ALERT_STATE_KEY = "system.openai.api_key_missing_alert"
_MISSING_API_KEY_ALERT_MESSAGE = (
    "\U0001f511 OpenAI-API-Schlüssel fehlt. Bitte `OPENAI_API_KEY` in der Umgebung oder in den Streamlit-Secrets hinterlegen.\n"
    "OpenAI API key not configured. Set OPENAI_API_KEY in the environment or Streamlit secrets."
)

_AUTHENTICATION_ERROR_MESSAGE = "OpenAI API key invalid or quota exceeded."
_RATE_LIMIT_ERROR_MESSAGE = "OpenAI API rate limit exceeded. Please retry later."
_NETWORK_ERROR_MESSAGE = "Network error communicating with OpenAI. Please check your connection and retry."
_INVALID_REQUEST_ERROR_MESSAGE = (
    "❌ An internal error occurred while processing your request. (The app made an invalid request to the AI model.)"
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


def _create_response_with_timeout(payload: Dict[str, Any]) -> Any:
    """Execute a Responses create call with configured timeout handling."""

    request_kwargs = dict(payload)
    timeout = request_kwargs.pop("timeout", OPENAI_REQUEST_TIMEOUT)
    if USE_CLASSIC_API:
        return get_client().chat.completions.create(timeout=timeout, **request_kwargs)
    return get_client().responses.create(timeout=timeout, **request_kwargs)


def _execute_response(payload: Dict[str, Any], model: Optional[str]) -> Any:
    """Send ``payload`` to the configured OpenAI API with retry handling."""

    with tracer.start_as_current_span("openai.execute_response") as span:
        if model:
            span.set_attribute("llm.model", model)
        span.set_attribute("llm.has_tools", "functions" in payload)
        if "temperature" in payload:
            temperature_value = payload.get("temperature")
            if isinstance(temperature_value, (int, float)):
                span.set_attribute("llm.temperature", float(temperature_value))
            elif temperature_value is not None:
                span.set_attribute("llm.temperature", str(temperature_value))
        try:
            return _create_response_with_timeout(payload)
        except BadRequestError as err:
            span.record_exception(err)
            if "temperature" in payload and _is_temperature_unsupported_error(err):
                span.add_event("retry_without_temperature")
                _mark_model_without_temperature(model)
                payload.pop("temperature", None)
                return _create_response_with_timeout(payload)
            if "reasoning" in payload and _is_reasoning_unsupported_error(err):
                span.add_event("retry_without_reasoning")
                _mark_model_without_reasoning(model)
                payload.pop("reasoning", None)
                return _create_response_with_timeout(payload)
            if model and _should_mark_model_unavailable(err):
                mark_model_unavailable(model)
            span.set_status(Status(StatusCode.ERROR, str(err)))
            raise
        except OpenAIError as err:
            span.record_exception(err)
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


def _normalise_usage(usage_obj: Any) -> dict:
    """Return a plain dictionary describing token usage."""

    if usage_obj and not isinstance(usage_obj, dict):
        usage: dict = getattr(usage_obj, "model_dump", getattr(usage_obj, "dict", lambda: {}))()
    else:
        usage = usage_obj if isinstance(usage_obj, dict) else {}

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


def _update_usage_counters(usage: Mapping[str, int], *, task: ModelTask | str | None) -> None:
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


def _collect_tool_calls_from_chat_completion(response: Any) -> list[dict]:
    """Extract tool calls from a Chat Completions response."""

    choices = getattr(response, "choices", None)
    if choices is None:
        response_map = _to_mapping(response)
        choices = response_map.get("choices") if response_map else None

    if not isinstance(choices, Sequence) or isinstance(choices, (str, bytes)):
        return []

    collected: list[dict] = []
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

                payload = {
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


def _collect_tool_calls(response: Any) -> list[dict]:
    """Extract tool call payloads from an OpenAI response object."""

    if hasattr(response, "choices") or (isinstance(response, Mapping) and "choices" in response):
        return _collect_tool_calls_from_chat_completion(response)

    tool_calls: list[dict] = []
    for item in getattr(response, "output", []) or []:
        data = _to_mapping(item)
        if not data:
            continue
        typ = str(data.get("type") or "")
        if not typ or ("tool_call" not in typ and "tool_response" not in typ):
            continue

        call_data = dict(data)
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

        if canonical_id:
            call_data["call_id"] = canonical_id
        tool_calls.append(call_data)
    return tool_calls


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


def _file_search_result_key(result: Mapping[str, Any]) -> Tuple[str, str, str]:
    """Return a deduplication key for a file-search result mapping."""

    chunk_id = str(result.get("id") or result.get("chunk_id") or "")
    file_id = str(result.get("file_id") or "")
    text_value = str(result.get("text") or "")
    return chunk_id, file_id, text_value


def _collect_file_search_results(response: Any) -> list[dict[str, Any]]:
    """Extract file-search results from a Responses API object."""

    collected: list[dict[str, Any]] = []
    seen: set[Tuple[str, str, str]] = set()

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
                normalised = dict(result_map)
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


def _merge_usage_dicts(
    primary_usage: Mapping[str, Any] | None,
    secondary_usage: Mapping[str, Any] | None,
) -> dict[str, int]:
    """Combine two usage dictionaries by summing numeric values."""

    combined: dict[str, int] = {}
    for usage in (primary_usage or {}, secondary_usage or {}):
        if not isinstance(usage, Mapping):
            continue
        for key, value in usage.items():
            combined[key] = combined.get(key, 0) + _coerce_token_count(value)
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
        for field in ("description", "parameters", "strict"):
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


def _prepare_payload(
    messages: Sequence[dict],
    *,
    model: Optional[str],
    temperature: float | None,
    max_tokens: int | None,
    json_schema: Optional[dict],
    tools: Optional[list],
    tool_choice: Optional[Any],
    tool_functions: Optional[Mapping[str, Callable[..., Any]]],
    reasoning_effort: Optional[str],
    extra: Optional[dict],
    include_analysis_tools: bool = True,
    task: ModelTask | str | None = None,
    previous_response_id: str | None = None,
) -> tuple[
    Dict[str, Any],
    str,
    list,
    dict[str, Callable[..., Any]],
    list[str],
]:
    """Assemble the payload for the configured OpenAI API."""

    selected_task = task or ModelTask.DEFAULT
    router_estimate = None
    candidate_override = model
    if model is None:
        base_model = get_model_for(selected_task)
        chosen_model, router_estimate = route_model_for_messages(messages, default_model=base_model)
        if chosen_model != base_model:
            candidate_override = chosen_model
            model = get_first_available_model(selected_task, override=chosen_model)
        else:
            model = base_model
    if reasoning_effort is None:
        reasoning_effort = st.session_state.get("reasoning_effort", REASONING_EFFORT)

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

        for field in ("description", "parameters", "strict"):
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
            prepared["name"] = function_name
            function_dict["name"] = function_name
        else:
            prepared.pop("name", None)

        prepared["type"] = "function"
        prepared["function"] = function_dict
        return prepared, bool(function_name)

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
    if include_analysis_tools:
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

    payload: dict[str, Any]

    if USE_CLASSIC_API:
        payload = {"model": model, "messages": messages_payload}
        if temperature is not None and model_supports_temperature(model):
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if json_schema is not None:
            schema_payload = dict(json_schema)
            if STRICT_JSON:
                schema_payload.setdefault("strict", True)
            format_config: dict[str, Any] = {
                "type": "json_schema",
                "json_schema": schema_payload,
            }
            payload["response_format"] = format_config
        if combined_tools:
            functions = _convert_tools_to_functions(combined_tools)
            if functions:
                payload["functions"] = functions
                function_call = _convert_tool_choice_to_function_call(normalised_tool_choice)
                if function_call is not None:
                    payload["function_call"] = function_call
    else:
        payload = {"model": model, "input": messages_payload}
        if previous_response_id:
            payload["previous_response_id"] = previous_response_id
        if temperature is not None and model_supports_temperature(model):
            payload["temperature"] = temperature
        if model_supports_reasoning(model):
            payload["reasoning"] = {"effort": reasoning_effort}
        if max_tokens is not None:
            payload["max_output_tokens"] = max_tokens
        if json_schema is not None:
            text_config: dict[str, Any] = dict(payload.get("text") or {})
            schema_payload = dict(json_schema)
            if STRICT_JSON:
                schema_payload.setdefault("strict", True)
            format_config = {
                "type": "json_schema",
                "json_schema": schema_payload,
            }
            text_config["format"] = format_config
            payload["text"] = text_config
        if combined_tools:
            responses_tools: list[dict[str, Any]] = []
            for tool_spec in combined_tools:
                cleaned_spec = dict(tool_spec)
                responses_tools.append(cleaned_spec)
            if responses_tools:
                payload["tools"] = responses_tools

        if normalised_tool_choice is not None:
            payload["tool_choice"] = normalised_tool_choice
        if extra:
            payload.update(extra)

        if router_estimate is not None:
            metadata: dict[str, Any] = dict(payload.get("metadata") or {})
            router_info: dict[str, Any] = dict(metadata.get("router") or {})
            router_info.update(
                {
                    "complexity": router_estimate.complexity.value,
                    "tokens": router_estimate.total_tokens,
                    "hard_words": router_estimate.hard_word_count,
                }
            )
            metadata["router"] = router_info
            payload["metadata"] = metadata

    return payload, model, combined_tools, tool_map, candidate_models


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
    tool_calls: list[dict]
    usage: dict
    response_id: str | None = None
    raw_response: Any | None = None
    file_search_results: Optional[list[dict[str, Any]]] = None
    secondary_content: Optional[str] = None
    secondary_tool_calls: Optional[list[dict]] = None
    secondary_usage: Optional[dict] = None
    comparison: Optional[dict[str, Any]] = None
    secondary_raw_response: Any | None = None
    secondary_file_search_results: Optional[list[dict[str, Any]]] = None
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
        try:
            if USE_CLASSIC_API:
                with client.chat.completions.stream(**self._payload) as stream:
                    for event in stream:
                        for chunk in _stream_event_chunks(event):
                            if chunk:
                                self._buffer.append(chunk)
                                yield chunk
                    final_response = stream.get_final_completion()
            else:
                with client.responses.stream(**self._payload) as stream:
                    for event in stream:
                        for chunk in _stream_event_chunks(event):
                            if chunk:
                                self._buffer.append(chunk)
                                yield chunk
                    final_response = stream.get_final_response()
        except (OpenAIError, RuntimeError) as error:
            _handle_streaming_error(error)
        else:
            self._finalise(final_response)

    def _finalise(self, response: Any) -> None:
        tool_calls = _collect_tool_calls(response)
        if tool_calls:
            raise RuntimeError(
                "Streaming responses requested tool execution. Use call_chat_api for tool-enabled prompts."
            )
        content = _extract_output_text(response)
        usage = _normalise_usage(_extract_usage_block(response) or {})
        _update_usage_counters(usage, task=self._task)
        response_id = _extract_response_id(response)
        self._result = ChatCallResult(
            content,
            tool_calls,
            usage,
            response_id=response_id,
        )

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
                chunks: list[str] = []
                for part in content:
                    part_map = _to_mapping(part)
                    if not part_map:
                        continue
                    text_value = part_map.get("text")
                    if isinstance(text_value, str):
                        chunks.append(text_value)
                if chunks:
                    return chunks

    return []


def get_client() -> OpenAI:
    """Return a configured OpenAI client."""

    global client
    if client is None:
        key = OPENAI_API_KEY
        if not key:
            _show_missing_api_key_alert()
            raise RuntimeError(
                "OpenAI API key not configured. Set OPENAI_API_KEY in the environment or Streamlit secrets."
            )
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
            emitter(_MISSING_API_KEY_ALERT_MESSAGE)
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
        return _AUTHENTICATION_ERROR_MESSAGE, _AUTHENTICATION_ERROR_MESSAGE

    if isinstance(error, RateLimitError):
        return _RATE_LIMIT_ERROR_MESSAGE, _RATE_LIMIT_ERROR_MESSAGE

    if isinstance(error, (APIConnectionError, APITimeoutError)):
        return _NETWORK_ERROR_MESSAGE, _NETWORK_ERROR_MESSAGE

    if isinstance(error, BadRequestError) or getattr(error, "type", "") == "invalid_request_error":
        detail = getattr(error, "message", str(error))
        log_msg = f"OpenAI invalid request: {detail}"
        return _INVALID_REQUEST_ERROR_MESSAGE, log_msg

    if isinstance(error, APIError):
        detail = getattr(error, "message", str(error))
        return f"OpenAI API error: {detail}", f"OpenAI API error: {detail}"

    return f"Unexpected OpenAI error: {error}", f"Unexpected OpenAI error: {error}"


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
        user_msg = _RATE_LIMIT_ERROR_MESSAGE
        log_msg = f"OpenAI streaming rate limit: {message}"
    elif any(keyword in lowered for keyword in ("timeout", "timed out", "connection", "network", "dns", "503", "504")):
        user_msg = _NETWORK_ERROR_MESSAGE
        log_msg = f"OpenAI streaming network error: {message}"
    elif any(
        keyword in lowered
        for keyword in ("invalid", "bad request", "prompt", "context length", "length limit", "unsupported")
    ):
        user_msg = _INVALID_REQUEST_ERROR_MESSAGE
        log_msg = f"OpenAI streaming invalid request: {message}"
    else:
        user_msg = f"Unexpected OpenAI error: {message}"
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
    max_tokens: int | None = None,
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

    payload, model, tools, tool_functions, candidate_models = _prepare_payload(
        messages_with_hint,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        json_schema=json_schema,
        tools=tools,
        tool_choice=tool_choice,
        tool_functions=tool_functions,
        reasoning_effort=reasoning_effort,
        extra=extra,
        task=task,
        previous_response_id=previous_response_id,
    )

    message_key = "messages" if "messages" in payload else "input"
    base_messages = payload.get(message_key)
    if isinstance(base_messages, list):
        messages_list = base_messages
    else:
        messages_list = list(messages_with_hint)
        payload[message_key] = messages_list

    unique_candidates: list[str] = []
    for candidate in [model, *candidate_models]:
        if candidate and candidate not in unique_candidates:
            unique_candidates.append(candidate)

    if not unique_candidates:
        raise RuntimeError("No model candidates resolved for call_chat_api request")

    attempted: set[str] = set()
    current_model = unique_candidates[0]
    payload["model"] = current_model

    accumulated_usage: dict[str, int] = {}
    last_tool_calls: list[dict] = []
    file_search_results: list[dict[str, Any]] = []
    seen_file_search: set[Tuple[str, str, str]] = set()

    while True:
        try:
            response = _execute_response(payload, current_model)
        except OpenAIError as err:
            attempted.add(current_model)
            if is_model_available(current_model):
                raise

            next_model: str | None = None
            for candidate in unique_candidates:
                if candidate in attempted:
                    continue
                if is_model_available(candidate):
                    next_model = candidate
                    break

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
        if response_id and not USE_CLASSIC_API:
            payload["previous_response_id"] = response_id

        content = _extract_output_text(response)

        tool_calls = _collect_tool_calls(response)

        usage = _normalise_usage(_extract_usage_block(response) or {})
        numeric_usage = {key: _coerce_token_count(value) for key, value in usage.items()}
        for key, value in numeric_usage.items():
            accumulated_usage[key] = accumulated_usage.get(key, 0) + value

        if capture_file_search:
            for entry in _collect_file_search_results(response):
                key = _file_search_result_key(entry)
                if key in seen_file_search:
                    continue
                seen_file_search.add(key)
                file_search_results.append(entry)

        if tool_calls:
            last_tool_calls = tool_calls

        if not tool_calls:
            merged_usage = dict(accumulated_usage) if accumulated_usage else numeric_usage
            _update_usage_counters(merged_usage, task=task)
            result_tool_calls = last_tool_calls
            return ChatCallResult(
                content,
                result_tool_calls,
                merged_usage,
                response_id=response_id,
                raw_response=response if include_raw_response else None,
                file_search_results=file_search_results if file_search_results else None,
            )

        executed = False
        tool_messages: list[dict[str, Any]] = []
        for call in tool_calls:
            call_type = str(call.get("type") or "")
            if "tool_response" in call_type:
                payload_text = call.get("output")
                if payload_text is None:
                    payload_text = call.get("content")
                serialised_payload = _serialise_tool_payload(payload_text)
                if serialised_payload is None:
                    continue
                tool_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("call_id") or call.get("id"),
                        "content": serialised_payload,
                    }
                )
                executed = True
                continue

            if not tool_functions:
                continue

            func_block = call.get("function")
            func_info = dict(func_block) if isinstance(func_block, Mapping) else {}
            name = func_info.get("name")
            if not name or name not in tool_functions:
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
            result = tool_functions[name](**args)
            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("call_id") or call.get("id") or name,
                    "content": json.dumps(result),
                }
            )
            executed = True

        if tool_messages:
            messages_list.extend(tool_messages)
            payload[message_key] = messages_list

        if not executed:
            merged_usage = dict(accumulated_usage) if accumulated_usage else numeric_usage
            _update_usage_counters(merged_usage, task=task)
            result_tool_calls = tool_calls or last_tool_calls
            return ChatCallResult(
                content,
                result_tool_calls,
                merged_usage,
                response_id=response_id,
                raw_response=response if include_raw_response else None,
                file_search_results=file_search_results if file_search_results else None,
            )


@backoff.on_exception(
    backoff.expo,
    (APITimeoutError, APIConnectionError, RateLimitError, APIError),
    max_tries=3,
    jitter=backoff.full_jitter,
    giveup=lambda exc: isinstance(exc, BadRequestError),
    on_giveup=_on_api_giveup,
)
def call_chat_api(
    messages: Sequence[dict],
    *,
    model: str | None = None,
    temperature: float | None = 0.2,
    max_tokens: int | None = None,
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

    single_kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
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
        "max_tokens",
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
        secondary_usage=dict(secondary_result.usage or {}),
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
    max_tokens: int | None = None,
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

    messages_with_hint = _inject_verbosity_hint(messages, _resolve_verbosity(verbosity))

    payload, model_name, tools, tool_functions, _candidate_models = _prepare_payload(
        messages_with_hint,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        json_schema=json_schema,
        tools=None,
        tool_choice=None,
        tool_functions=None,
        reasoning_effort=reasoning_effort,
        extra=extra,
        include_analysis_tools=False,
        task=task,
    )

    if tools or tool_functions:
        raise ValueError("Streaming responses do not support tool execution.")

    return ChatStream(payload, model_name, task=task)


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
]
