"""High-level OpenAI API facade and chat helpers.

This module orchestrates the dedicated OpenAI helpers:

* :mod:`openai_utils.payloads` for assembling request payloads.
* :class:`openai_utils.client.OpenAIClient` for network execution and retries.
* :mod:`openai_utils.schemas` for JSON schema preparation.
* :mod:`openai_utils.tools` for handling tool calls and execution loops.

It exposes :func:`call_chat_api`, which wires these pieces together to call the
Responses or Chat Completions APIs while executing requested tools and feeding
results back to the model.
"""

from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from difflib import SequenceMatcher
from threading import Lock
from typing import Any, Callable, Dict, Final, Iterable, Iterator, Mapping, MutableMapping, Optional, Sequence, cast

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
    OPENAI_REQUEST_TIMEOUT,
    OPENAI_SESSION_TOKEN_LIMIT,
    APIMode,
    ModelTask,
    VERBOSITY,
    get_active_verbosity,
    is_model_available,
    mark_model_unavailable,
    normalise_verbosity,
    resolve_api_mode,
)
from constants.keys import StateKeys
from utils.errors import display_error, resolve_message
from utils.i18n import tr
from utils.json_repair import JsonRepairStatus, parse_json_with_repair
from utils.llm_state import llm_disabled_message
from utils.logging_context import log_context, set_model
from utils.retry import retry_with_backoff
from .client import (
    FileSearchKey,
    FileSearchResult,
    ResponsesRequest,
    RetryState,
    ToolCallPayload,
    UsageDict,
    OpenAIClient,
    build_fallback_context,
    create_retry_state,
    model_supports_reasoning,
    model_supports_temperature,
    USER_FRIENDLY_TIMEOUT_SECONDS,
    _mark_model_without_reasoning,  # noqa: F401
    _mark_model_without_temperature,  # noqa: F401
)
from .errors import (
    ExternalServiceError,
    LLMResponseFormatError,
    LLMTimeoutError,
    NeedAnalysisPipelineError,
    SchemaValidationError,
)
from .payloads import (
    ChatPayloadBuilder,  # noqa: F401
    PayloadContext,  # noqa: F401
    ResponsesPayloadBuilder,  # noqa: F401
    _build_chat_fallback_payload,
    _convert_responses_payload_to_chat,
    _prepare_payload,
)
from .schemas import (
    SchemaFormatBundle,
    build_need_analysis_json_schema_payload,  # noqa: F401
    build_schema_format_bundle,
)
from .tools import _execute_tool_invocations, _serialise_tool_payload

logger = logging.getLogger("cognitive_needs.openai")

openai_client = OpenAIClient()
client = openai_client
_create_response_with_timeout = openai_client._create_response_with_timeout

_USAGE_LOCK = Lock()
_FALLBACK_USAGE_COUNTERS: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}
_BUDGET_GUARD_ALERT_STATE_KEY = "system.openai.budget_guard_alert"
_BUDGET_EXCEEDED_MESSAGE: Final[tuple[str, str]] = (
    "Budget-Limit erreicht ({limit} Token pro Sitzung). Bitte Eingaben prüfen oder Budget erhöhen.",
    "Cost limit reached ({limit} tokens per session). Please review your inputs or raise the budget.",
)
_CURRENT_USAGE_MESSAGE: Final[tuple[str, str]] = (
    "Aktuelle Nutzung: {total} Token.",
    "Current usage: {total} tokens.",
)
_budget_exceeded_flag = False

DEFAULT_TEMPERATURE: Final[float] = 0.1

_TEXT_ONLY_TASKS: Final[set[ModelTask]] = {
    ModelTask.FOLLOW_UP_QUESTIONS,
    ModelTask.TEAM_ADVICE,
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
_TIMEOUT_ERROR_MESSAGE: Final[tuple[str, str]] = (
    "⏳ Die Anfrage dauert länger als erwartet. Bitte erneut versuchen oder die Felder manuell ausfüllen.",
    "⏳ This is taking longer than usual. Please try again or continue filling the fields manually.",
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


def _log_known_openai_error(error: OpenAIError, api_mode: str) -> None:
    """Record additional context for known, non-retriable OpenAI failures."""

    if is_unrecoverable_schema_error(error):
        logger.error(
            "OpenAI rejected JSON schema for %s request; skipping retries: %s",
            api_mode,
            getattr(error, "message", str(error)),
        )


def _should_abort_retry(error: Exception) -> bool:
    """Return ``True`` when retries should stop to allow model fallback."""

    if isinstance(error, OpenAIError) and _is_parameter_unsupported_error(error, "response_format"):
        return True
    return is_unrecoverable_schema_error(error) or isinstance(error, APITimeoutError)


def _execute_response(
    payload: Dict[str, Any],
    model: Optional[str],
    *,
    api_mode: APIMode | str | bool | None = None,
) -> Any:
    """Send ``payload`` to the configured OpenAI API with retry handling."""

    mode_value = resolve_api_mode(api_mode).value
    return openai_client.execute_request(
        payload,
        model,
        api_mode=mode_value,
        giveup=_should_abort_retry,
        on_giveup=_on_api_giveup,
        on_known_error=_log_known_openai_error,
    )


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


def _normalise_content_payload(content: Any) -> str | None:
    """Coerce ``content`` into a serialisable string when possible."""

    if content is None:
        return None

    if isinstance(content, Mapping):
        try:
            return json.dumps(dict(content), ensure_ascii=False)
        except TypeError:
            return str(content)

    if isinstance(content, str):
        stripped = content.strip()
        if not stripped:
            return stripped
        if stripped.startswith(("{", "[")):
            try:
                loaded = json.loads(stripped)
            except json.JSONDecodeError:
                return stripped
            try:
                return json.dumps(loaded, ensure_ascii=False)
            except TypeError:
                return stripped
        return stripped

    return str(content)


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


def _token_budget_limit() -> int | None:
    """Return the configured per-session token ceiling or ``None`` when disabled."""

    try:
        limit = int(OPENAI_SESSION_TOKEN_LIMIT) if OPENAI_SESSION_TOKEN_LIMIT is not None else None
    except (TypeError, ValueError):
        return None
    if limit is None:
        return None
    if limit <= 0:
        return None
    return limit


def _budget_guard_message(limit: int, total: int | None = None) -> str:
    """Return a bilingual budget warning message with optional usage total."""

    base = tr(*_BUDGET_EXCEEDED_MESSAGE).format(limit=limit)
    if total is None:
        return base
    return f"{base} {tr(*_CURRENT_USAGE_MESSAGE).format(total=total)}"


def _current_usage_total_locked(usage_state: Mapping[str, Any] | None = None) -> int:
    """Return the total token count using session or fallback counters."""

    fallback_total = _coerce_token_count(_FALLBACK_USAGE_COUNTERS.get("input_tokens")) + _coerce_token_count(
        _FALLBACK_USAGE_COUNTERS.get("output_tokens")
    )
    if usage_state is None:
        try:
            usage_state = st.session_state.get(StateKeys.USAGE)
        except Exception:  # pragma: no cover - Streamlit session not initialised
            usage_state = None
    if not isinstance(usage_state, Mapping):
        return fallback_total
    input_tokens = _coerce_token_count(usage_state.get("input_tokens"))
    output_tokens = _coerce_token_count(usage_state.get("output_tokens"))
    return input_tokens + output_tokens


def _mark_budget_exceeded_locked() -> None:
    """Record that the session has crossed the configured budget limit."""

    global _budget_exceeded_flag
    _budget_exceeded_flag = True
    try:
        st.session_state[StateKeys.USAGE_BUDGET_EXCEEDED] = True
    except Exception:  # pragma: no cover - Streamlit session not initialised
        pass


def _show_budget_guard_warning(limit: int, total: int) -> None:
    """Emit a user-facing warning when the budget guard is hit."""

    try:
        if st.session_state.get(_BUDGET_GUARD_ALERT_STATE_KEY):
            return
    except Exception:  # pragma: no cover - Streamlit session not initialised
        pass

    message = _budget_guard_message(limit, total)
    emitted = False
    for emitter in (display_error, getattr(st, "warning", None), getattr(st, "error", None)):
        if emitter is None:
            continue
        try:
            emitter(message)
            emitted = True
            break
        except Exception:  # noqa: BLE001 - fall back to the next emitter
            continue

    if emitted:
        try:
            st.session_state[_BUDGET_GUARD_ALERT_STATE_KEY] = True
        except Exception:  # pragma: no cover - Streamlit session not initialised
            pass

    logger.warning("Token budget guard engaged (usage=%s, limit=%s)", total, limit)


def _enforce_usage_budget_guard() -> None:
    """Raise when the configured token budget has already been exhausted."""

    limit = _token_budget_limit()
    if limit is None:
        return

    exceeded = False
    total = 0
    with _USAGE_LOCK:
        total = _current_usage_total_locked()
        exceeded = _budget_exceeded_flag or total >= limit
        if exceeded and not _budget_exceeded_flag:
            _mark_budget_exceeded_locked()

    if exceeded:
        _show_budget_guard_warning(limit, total)
        raise RuntimeError(_budget_guard_message(limit, total))


def _normalise_task(task: ModelTask | str | None) -> str:
    """Return a normalised identifier for ``task`` suitable for metrics."""

    if isinstance(task, ModelTask):
        return task.value
    if isinstance(task, str) and task.strip():
        return task.strip()
    return ModelTask.DEFAULT.value


def _update_usage_counters(usage: Mapping[str, Any], *, task: ModelTask | str | None) -> None:
    """Accumulate token usage in the Streamlit session state."""

    limit = _token_budget_limit()
    crossed_threshold = False
    total_after_update = 0

    with _USAGE_LOCK:
        input_tokens = _coerce_token_count(usage.get("input_tokens"))
        output_tokens = _coerce_token_count(usage.get("output_tokens"))

        _FALLBACK_USAGE_COUNTERS["input_tokens"] = (
            _coerce_token_count(_FALLBACK_USAGE_COUNTERS.get("input_tokens", 0)) + input_tokens
        )
        _FALLBACK_USAGE_COUNTERS["output_tokens"] = (
            _coerce_token_count(_FALLBACK_USAGE_COUNTERS.get("output_tokens", 0)) + output_tokens
        )

        usage_state: MutableMapping[str, Any] | None = None
        try:
            usage_candidate = st.session_state.get(StateKeys.USAGE)
        except Exception:  # pragma: no cover - Streamlit session not initialised
            usage_candidate = None

        if isinstance(usage_candidate, MutableMapping):
            usage_state = usage_candidate
        elif isinstance(usage_candidate, Mapping):
            usage_state = dict(usage_candidate)
            try:
                st.session_state[StateKeys.USAGE] = usage_state
            except Exception:  # pragma: no cover - Streamlit session not initialised
                pass

        if usage_state is not None:
            usage_state["input_tokens"] = _coerce_token_count(usage_state.get("input_tokens", 0)) + input_tokens
            usage_state["output_tokens"] = _coerce_token_count(usage_state.get("output_tokens", 0)) + output_tokens

            task_key = _normalise_task(task)
            task_map = usage_state.setdefault("by_task", {})
            task_totals = task_map.setdefault(task_key, {"input": 0, "output": 0})
            task_totals["input"] = _coerce_token_count(task_totals.get("input", 0)) + input_tokens
            task_totals["output"] = _coerce_token_count(task_totals.get("output", 0)) + output_tokens

        total_after_update = _current_usage_total_locked(usage_state)
        if limit is not None and not _budget_exceeded_flag and total_after_update >= limit:
            crossed_threshold = True
            _mark_budget_exceeded_locked()

    if crossed_threshold and limit is not None:
        _show_budget_guard_warning(limit, total_after_update)


def _accumulate_usage(state: RetryState, latest: UsageDict) -> None:
    """Add ``latest`` token counts to ``state``."""

    for key, value in latest.items():
        state.accumulated_usage[key] = state.accumulated_usage.get(key, 0) + value


def _usage_snapshot(state: RetryState, latest: UsageDict) -> UsageDict:
    """Return the merged usage totals after accounting for retries."""

    if state.accumulated_usage:
        return dict(state.accumulated_usage)
    return dict(latest)


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
    low_confidence: bool = False
    repair_status: JsonRepairStatus | None = None


ComparisonBuilder = Callable[["ChatCallResult", "ChatCallResult"], Mapping[str, Any]]


class ChatStream(Iterable[str]):
    """Iterator over streaming chat responses."""

    def __init__(
        self,
        payload: Dict[str, Any],
        model: str,
        *,
        task: ModelTask | str | None,
        api_mode: APIMode | str | bool | None = None,
    ):
        prepared_payload = dict(payload)
        prepared_payload.setdefault("timeout", OPENAI_REQUEST_TIMEOUT)
        self._payload = prepared_payload
        self._model = model
        self._task = task
        self._api_mode = resolve_api_mode(api_mode)
        self._result: ChatCallResult | None = None
        self._buffer: list[str] = []

    def __iter__(self) -> Iterator[str]:
        yield from self._consume()

    def _consume(self) -> Iterator[str]:
        client = get_client()
        context_model = str(self._payload.get("model") or "").strip() or None
        schema_name: str | None = None
        response_format = self._payload.get("response_format")
        if isinstance(response_format, Mapping):
            schema_name = (
                str(response_format.get("name") or response_format.get("json_schema", {}).get("name") or "").strip()
                or None
            )
        with log_context(pipeline_task=str(self._task) if self._task is not None else None, model=context_model):
            set_model(context_model)
            if not self._api_mode.is_classic and _has_strict_json_schema_format(self._payload):
                logger.info(
                    "Strict JSON schema detected for streaming request; retrying without streaming.",
                )
                recovered_response = self._retry_responses_without_stream(client)
                if recovered_response is None:
                    recovered_response = self._retry_chat_completion(client)

                if recovered_response is None:
                    _handle_streaming_error(
                        RuntimeError("Streaming is unavailable for strict JSON schema payloads."),
                        model=context_model,
                        schema_name=schema_name,
                        step=str(self._task),
                        api_mode=self._api_mode.value,
                    )
                    return

                self._finalise(recovered_response)
                return

            final_response: Any | None = None
            missing_completion_event = False
            try:
                if self._api_mode.is_classic:
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
                        _handle_streaming_error(
                            error,
                            model=context_model,
                            schema_name=schema_name,
                            step=str(self._task),
                            api_mode=self._api_mode.value,
                        )
                        return
                else:
                    _handle_streaming_error(
                        error,
                        model=context_model,
                        schema_name=schema_name,
                        step=str(self._task),
                        api_mode=self._api_mode.value,
                    )
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

            if (self._result is None or not (self._result.content or "").strip()) and not self._api_mode.is_classic:
                fallback = self._retry_chat_completion(client)
                if fallback is not None:
                    logger.warning(
                        "Streaming returned empty content; falling back to chat completions.",
                    )
                    self._finalise(fallback)

    def _recover_stream_response(self, client: OpenAI) -> Any | None:
        """Return a non-streamed payload to finalise the request if possible."""

        if self._api_mode.is_classic:
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
        content = _normalise_content_payload(content)
        usage_block = _normalise_usage(_extract_usage_block(response) or {})
        usage = _numeric_usage(usage_block)
        usage_limit = self._payload.get("max_output_tokens") or self._payload.get("max_completion_tokens")
        logger.info(
            "OpenAI usage for task '%s' (model=%s, max_tokens=%s): input=%s, output=%s, total=%s.",
            self._task or ModelTask.DEFAULT,
            self._payload.get("model"),
            usage_limit,
            usage.get("input_tokens"),
            usage.get("output_tokens"),
            usage.get("total_tokens"),
        )
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


def _has_strict_json_schema_format(payload: Mapping[str, Any]) -> bool:
    """Return ``True`` when ``payload`` enforces strict JSON schema output."""

    def _is_strict_json(candidate: Mapping[str, Any] | None) -> bool:
        mapping = _to_mapping(candidate)
        if not mapping:
            return False
        if str(mapping.get("type") or "").lower() != "json_schema":
            return False
        json_schema = mapping.get("json_schema") if isinstance(mapping, Mapping) else None
        strict_flag: Any | None = None
        if isinstance(json_schema, Mapping):
            strict_flag = json_schema.get("strict")
        if strict_flag is None:
            strict_flag = mapping.get("strict")
        return bool(strict_flag)

    text_block = payload.get("text")
    if isinstance(text_block, Mapping) and _is_strict_json(text_block.get("format")):
        return True

    return _is_strict_json(payload.get("response_format"))


def _is_missing_completion_event_error(error: BaseException | None) -> bool:
    """Return ``True`` when ``error`` indicates a missing completion event."""

    if not error:
        return False
    message = str(error)
    if not message:
        return False
    lowered = message.lower()
    return "response.completed" in lowered or "completion event" in lowered


def get_client() -> OpenAI:
    """Return a configured OpenAI client."""

    try:
        return openai_client.get_client()
    except RuntimeError:
        _show_missing_api_key_alert()
        raise


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

    if isinstance(error, APITimeoutError):
        detail = getattr(error, "message", str(error))
        return (
            resolve_message(_TIMEOUT_ERROR_MESSAGE),
            f"OpenAI timeout error: {detail}",
        )

    if isinstance(error, APIConnectionError):
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


def _wrap_openai_exception(
    error: OpenAIError,
    *,
    model: str | None,
    schema_name: str | None,
    step: str | None,
    api_mode: str,
) -> NeedAnalysisPipelineError:
    """Translate OpenAI SDK errors into domain-specific exceptions."""

    message = getattr(error, "message", str(error))
    details: dict[str, Any] = {
        "api_mode": api_mode,
        "schema": schema_name,
    }
    if isinstance(error, BadRequestError) and is_unrecoverable_schema_error(error):
        return SchemaValidationError(
            resolve_message(_INVALID_REQUEST_ERROR_MESSAGE),
            step=step,
            model=model,
            details=details,
            schema=schema_name,
            original=error,
        )

    if isinstance(error, APITimeoutError):
        return LLMTimeoutError(
            resolve_message(_TIMEOUT_ERROR_MESSAGE),
            step=step,
            model=model,
            details={
                **details,
                "error_type": error.__class__.__name__,
                "timeout_seconds": USER_FRIENDLY_TIMEOUT_SECONDS,
            },
            schema=schema_name,
            original=error,
            timeout_seconds=USER_FRIENDLY_TIMEOUT_SECONDS,
        )

    return ExternalServiceError(
        resolve_message(_NETWORK_ERROR_MESSAGE if isinstance(error, APIConnectionError) else _RATE_LIMIT_ERROR_MESSAGE)
        if isinstance(error, (RateLimitError, APIConnectionError))
        else resolve_message((f"OpenAI-Fehler: {message}", f"OpenAI error: {message}")),
        step=step,
        model=model,
        details={**details, "error_type": error.__class__.__name__},
        service="openai",
        original=error,
    )


def _handle_openai_error(
    error: OpenAIError,
    *,
    model: str | None,
    schema_name: str | None,
    step: str | None,
    api_mode: str,
) -> None:
    """Raise a user-friendly domain error for OpenAI failures."""

    user_msg, log_msg = _describe_openai_error(error)
    wrapped = _wrap_openai_exception(error, model=model, schema_name=schema_name, step=step, api_mode=api_mode)
    logger.error(
        "%s (%s)", log_msg, wrapped.__class__.__name__, exc_info=error, extra={"schema": schema_name, "step": step}
    )
    try:  # pragma: no cover - Streamlit may not be initialised in tests
        st.error(user_msg)
    except Exception:  # noqa: BLE001
        pass
    raise wrapped from error


def _handle_streaming_error(
    error: Exception,
    *,
    model: str | None = None,
    schema_name: str | None = None,
    step: str | None = None,
    api_mode: str = "responses",
) -> None:
    """Surface streaming failures with user-facing feedback before re-raising."""

    if isinstance(error, OpenAIError):
        _handle_openai_error(error, model=model, schema_name=schema_name, step=step, api_mode=api_mode)
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
    logger.error(
        "Streaming error encountered (%s)",
        error.__class__.__name__,
        exc_info=error,
        extra={"schema": schema_name, "step": step},
    )
    raise ExternalServiceError(
        user_msg,
        step=step,
        model=model,
        details={"schema": schema_name, "api_mode": api_mode},
        service="openai",
        original=error,
    ) from error


def _on_api_giveup(details: Any) -> None:
    """Handle a final API error after retries have been exhausted."""

    err = details.get("exception")
    if isinstance(err, APITimeoutError):
        raise err
    if isinstance(err, BadRequestError):
        raise SchemaValidationError(
            resolve_message(_INVALID_REQUEST_ERROR_MESSAGE),
            schema=None,
            model=None,
            step=None,
            details={},
            original=err,
        )
    if isinstance(err, OpenAIError):  # pragma: no cover - defensive
        _handle_openai_error(err, model=None, schema_name=None, step=None, api_mode="chat")
    raise err  # pragma: no cover - re-raise unexpected errors


def build_chat_payload(
    messages: Sequence[Mapping[str, Any]],
    *,
    model: str | None = None,
    temperature: float | None = DEFAULT_TEMPERATURE,
    max_completion_tokens: int | None = None,
    json_schema: Optional[dict] = None,
    tools: Optional[list] = None,
    tool_choice: Optional[Any] = None,
    tool_functions: Optional[Mapping[str, Callable[..., Any]]] = None,
    reasoning_effort: str | None = None,
    verbosity: str | None = None,
    extra: Optional[dict] = None,
    include_analysis_tools: bool = True,
    task: ModelTask | str | None = None,
    previous_response_id: str | None = None,
    api_mode: APIMode | str | bool | None = None,
    use_response_format: bool = True,
) -> ResponsesRequest:
    """Return a prepared OpenAI payload without executing the request."""

    messages_with_hint = _inject_verbosity_hint(messages, _resolve_verbosity(verbosity))

    return _prepare_payload(
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
        include_analysis_tools=include_analysis_tools,
        task=task,
        previous_response_id=previous_response_id,
        api_mode=api_mode,
        use_response_format=use_response_format,
    )


def _call_chat_api_single(
    messages: Sequence[dict],
    *,
    model: str | None = None,
    temperature: float | None = DEFAULT_TEMPERATURE,
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
    api_mode: APIMode | str | bool | None = None,
    use_response_format: bool = True,
) -> ChatCallResult:
    """Execute a single chat completion call with optional tool handling."""

    active_mode = resolve_api_mode(api_mode)
    step_label = str(task.value) if isinstance(task, ModelTask) else str(task) if task is not None else None
    request = build_chat_payload(
        messages,
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
        api_mode=active_mode,
        use_response_format=use_response_format,
    )

    payload = dict(request.payload)
    api_mode_override = request.api_mode_override
    if api_mode_override is not None:
        active_mode = resolve_api_mode(api_mode_override)

    schema_bundle: SchemaFormatBundle | None = None
    if json_schema is not None and use_response_format:
        schema_bundle = build_schema_format_bundle(json_schema)
    schema_name = schema_bundle.name if schema_bundle is not None else None

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

    with log_context(pipeline_task=step_label, model=current_model):
        set_model(current_model)
        retry_state = create_retry_state()
        fallback_to_chat_attempted = False
        chat_retry_attempts = 0
        max_chat_retries = 2
        timed_out_models: set[str] = set()

        while True:
            with log_context(model=current_model):
                try:
                    response = _execute_response(payload, current_model, api_mode=api_mode_override)
                except OpenAIError as err:
                    schema_error = isinstance(err, BadRequestError) and is_unrecoverable_schema_error(err)
                    log_level = logger.warning if not schema_error else logger.error
                    log_level(
                        "OpenAI %s call failed for model %s: %s",
                        active_mode.value,
                        current_model,
                        getattr(err, "message", str(err)),
                        exc_info=err,
                    )

                    timed_out = isinstance(err, APITimeoutError)
                    if timed_out:
                        if current_model not in timed_out_models:
                            timed_out_models.add(current_model)
                            mark_model_unavailable(current_model)
                        try:  # pragma: no cover - Streamlit may not be initialised
                            st.warning(resolve_message(_TIMEOUT_ERROR_MESSAGE))
                        except Exception:  # noqa: BLE001
                            pass
                        next_model = context.register_failure(current_model)
                        if next_model is None:
                            raise _wrap_openai_exception(
                                err,
                                model=current_model,
                                schema_name=schema_name,
                                step=step_label,
                                api_mode=active_mode.value,
                            )

                        logger.warning(
                            "Model '%s' unavailable after timeout; retrying with fallback '%s'.",
                            current_model,
                            next_model,
                        )
                        payload["model"] = next_model
                        current_model = next_model
                        set_model(current_model)
                        continue

                    if not active_mode.is_classic and (schema_error or not fallback_to_chat_attempted):
                        fallback_to_chat_attempted = True
                        fallback_payload = _build_chat_fallback_payload(
                            payload,
                            messages_list,
                            schema_bundle,
                        )
                        if fallback_payload:
                            logger.info(
                                "%s; using Chat Completions fallback for model %s.",
                                "Responses schema rejected" if schema_error else "Responses API failed",
                                current_model,
                            )
                            try:
                                response = get_client().chat.completions.create(**fallback_payload)
                            except OpenAIError as chat_error:
                                logger.error(
                                    "Chat Completions fallback failed: %s",
                                    getattr(chat_error, "message", str(chat_error)),
                                    exc_info=chat_error,
                                )
                                response = None
                        else:
                            response = None
                        if response is None:
                            raise _wrap_openai_exception(
                                err,
                                model=current_model,
                                schema_name=schema_name,
                                step=step_label,
                                api_mode=active_mode.value,
                            )
                    elif active_mode.is_classic and chat_retry_attempts < max_chat_retries:
                        delay = 0.5 * (2**chat_retry_attempts)
                        chat_retry_attempts += 1
                        logger.info(
                            "Retrying Chat Completions after error (attempt %d/%d) in %.1fs.",
                            chat_retry_attempts,
                            max_chat_retries,
                            delay,
                        )
                        time.sleep(delay)
                        continue
                    elif is_model_available(current_model):
                        raise _wrap_openai_exception(
                            err,
                            model=current_model,
                            schema_name=schema_name,
                            step=step_label,
                            api_mode=active_mode.value,
                        )
                    else:
                        next_model = context.register_failure(current_model)

                        if next_model is None:
                            raise _wrap_openai_exception(
                                err,
                                model=current_model,
                                schema_name=schema_name,
                                step=step_label,
                                api_mode=active_mode.value,
                            )

                        logger.warning(
                            "Model '%s' unavailable (%s); retrying with fallback '%s'.",
                            current_model,
                            getattr(err, "message", str(err)),
                            next_model,
                        )
                        payload["model"] = next_model
                        current_model = next_model
                        set_model(current_model)
                        continue

            response_id = _extract_response_id(response)
            if response_id and not active_mode.is_classic and api_mode_override != "chat":
                payload["previous_response_id"] = response_id

            content = _extract_output_text(response)
            normalised_content = _normalise_content_payload(content)
            low_confidence = False
            repair_status: JsonRepairStatus | None = None

            comparison_messages: Sequence[dict] | None = None
            comparison_result: ChatCallResult | None = None
            comparison_label: str | None = None
            options: Mapping[str, Any] = {}
            metadata_builder: Callable[..., Any] | None = None
            primary_result: ChatCallResult | None = None
            usage_block = _normalise_usage(_extract_usage_block(response) or {})
            numeric_usage = _numeric_usage(usage_block)
            tool_calls = _collect_tool_calls(response)
            result_tool_calls = tool_calls

            if schema_bundle is not None and normalised_content:
                repair_attempt = parse_json_with_repair(normalised_content)
                repair_status = repair_attempt.status
                if repair_attempt.payload is not None:
                    normalised_content = json.dumps(repair_attempt.payload, ensure_ascii=False)
                if repair_attempt.status is JsonRepairStatus.FAILED and not active_mode.is_classic:
                    logger.warning(
                        "Structured extraction JSON parse failed during %s; retrying via chat.",
                        current_model,
                    )
                    fallback_payload = _build_chat_fallback_payload(payload, messages_list, schema_bundle)
                    if fallback_payload:
                        fallback_to_chat_attempted = True
                        try:
                            fallback_response = get_client().chat.completions.create(**fallback_payload)
                            fallback_content = _normalise_content_payload(_extract_output_text(fallback_response))
                            repair_attempt = parse_json_with_repair(fallback_content or "")
                            repair_status = repair_attempt.status
                            if repair_attempt.payload is not None:
                                normalised_content = json.dumps(repair_attempt.payload, ensure_ascii=False)
                            elif fallback_content:
                                normalised_content = fallback_content
                        except Exception as exc:  # pragma: no cover - defensive
                            logger.warning("Chat fallback after repair failure failed: %s", exc)
                    else:
                        logger.warning(
                            "Structured extraction parse failed for %s without chat fallback payload; returning raw content.",
                            current_model,
                        )
                low_confidence = repair_attempt.status is JsonRepairStatus.REPAIRED
            elif schema_bundle is not None and not normalised_content:
                raise LLMResponseFormatError(
                    "Model output could not be parsed into the expected schema.",
                    step=step_label,
                    model=current_model,
                    details={"schema": schema_name, "api_mode": active_mode.value},
                )

            normalised_secondary_content: str | None = None
            comparison_metadata: Mapping[str, Any] | None = None
            _comparison_responses: tuple[Any, Any] | None = None
            secondary_usage: UsageDict | None = None

            if comparison_messages is not None and comparison_result is not None and primary_result is not None:
                comparison_content = _normalise_content_payload(_extract_output_text(comparison_result.raw_response))
                normalised_secondary_content = comparison_content
                if schema_bundle is not None and comparison_content:
                    repair_attempt = parse_json_with_repair(comparison_content)
                    if repair_attempt.payload is not None:
                        normalised_secondary_content = json.dumps(repair_attempt.payload, ensure_ascii=False)
                    comparison_metadata = _build_comparison_metadata(
                        primary=primary_result,
                        secondary=comparison_result,
                        label=comparison_label,
                        custom=options.get("metadata_builder", metadata_builder),
                    )
                _comparison_responses = (response, comparison_result.raw_response)
                secondary_usage = comparison_result.usage

            merged_usage = _usage_snapshot(retry_state, numeric_usage)
            _update_usage_counters(merged_usage, task=task)
            return ChatCallResult(
                normalised_content,
                result_tool_calls,
                merged_usage,
                response_id=response_id,
                raw_response=response if include_raw_response else None,
                file_search_results=retry_state.file_search_results or None,
                secondary_content=normalised_secondary_content,
                secondary_tool_calls=comparison_result.secondary_tool_calls if comparison_result else None,
                secondary_usage=secondary_usage,
                comparison=comparison_metadata,
                secondary_raw_response=comparison_result.raw_response if comparison_result else None,
                secondary_file_search_results=comparison_result.file_search_results if comparison_result else None,
                secondary_response_id=comparison_result.response_id if comparison_result else None,
                low_confidence=low_confidence,
                repair_status=repair_status,
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
                normalised_content,
                result_tool_calls,
                merged_usage,
                response_id=response_id,
                raw_response=response if include_raw_response else None,
                file_search_results=retry_state.file_search_results or None,
                low_confidence=low_confidence,
                repair_status=repair_status,
            )


@retry_with_backoff(
    giveup=lambda exc: isinstance(exc, (BadRequestError, SchemaValidationError, LLMResponseFormatError))
    or is_unrecoverable_schema_error(exc),
    on_giveup=_on_api_giveup,
)
def call_chat_api(
    messages: Sequence[dict],
    *,
    model: str | None = None,
    temperature: float | None = DEFAULT_TEMPERATURE,
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
    api_mode: APIMode | str | bool | None = None,
    comparison_messages: Sequence[dict] | None = None,
    comparison_options: Optional[Mapping[str, Any]] = None,
    comparison_label: str | None = None,
    use_response_format: bool = True,
) -> ChatCallResult:
    """Call the OpenAI chat endpoint and return a :class:`ChatCallResult`.

    The function automatically targets either the Responses API or the classic
    Chat Completions API depending on configuration. When
    ``api_mode`` is provided, the override is honoured for both the primary and
    comparison calls without mutating global configuration. When
    ``comparison_messages`` are supplied a second request is dispatched in
    parallel (unless ``comparison_options['dispatch']`` is set to
    ``"sequential"``). Both responses are returned along with basic similarity
    metadata so callers can decide which variant to keep.
    """

    if _llm_disabled():
        _show_missing_api_key_alert()
        raise RuntimeError(llm_disabled_message())

    _enforce_usage_budget_guard()

    force_text_only = isinstance(task, ModelTask) and task in _TEXT_ONLY_TASKS
    if force_text_only:
        json_schema = None
        use_response_format = False

    active_mode = resolve_api_mode(api_mode)
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
        "api_mode": active_mode,
        "use_response_format": use_response_format,
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
        "use_response_format",
    }

    secondary_kwargs = dict(single_kwargs)
    for key in list(options):
        if key in allowed_override_keys:
            secondary_kwargs[key] = options.pop(key)

    if options:
        remaining = ", ".join(sorted(options.keys()))
        raise ValueError(f"Unsupported comparison_options keys: {remaining}")

    if force_text_only:
        secondary_kwargs["json_schema"] = None
        secondary_kwargs["use_response_format"] = False

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
    temperature: float | None = DEFAULT_TEMPERATURE,
    max_completion_tokens: int | None = None,
    json_schema: Optional[dict] = None,
    reasoning_effort: str | None = None,
    verbosity: str | None = None,
    extra: Optional[dict] = None,
    task: ModelTask | str | None = None,
    api_mode: APIMode | str | bool | None = None,
) -> ChatStream:
    """Return a :class:`ChatStream` yielding incremental text deltas.

    Streaming currently supports plain text generations without tool execution.
    ``tools``/``tool_functions`` are intentionally not accepted to avoid
    partially-executed tool calls.
    """

    if _llm_disabled():
        _show_missing_api_key_alert()
        raise RuntimeError(llm_disabled_message())

    _enforce_usage_budget_guard()

    active_mode = resolve_api_mode(api_mode)

    request = build_chat_payload(
        messages,
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
        api_mode=active_mode,
    )

    if request.tool_specs or request.tool_functions:
        raise ValueError("Streaming responses do not support tool execution.")

    if not request.model:
        raise RuntimeError("No model resolved for streaming request")

    return ChatStream(request.payload, request.model, task=task, api_mode=request.api_mode_override or active_mode)


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
    "build_chat_payload",
    "model_supports_reasoning",
    "model_supports_temperature",
    "_chat_content",
    "build_need_analysis_json_schema_payload",
    "SchemaFormatBundle",
    "build_schema_format_bundle",
    "is_unrecoverable_schema_error",
]
