from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable, Mapping, Sequence, TypedDict, TypeAlias

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from openai import BadRequestError, OpenAI, OpenAIError
import streamlit as st

from config import (
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_ORGANIZATION,
    OPENAI_PROJECT,
    OPENAI_REQUEST_TIMEOUT,
    mark_model_unavailable,
)
from utils.errors import display_error, resolve_message
from utils.retry import retry_with_backoff
from .schemas import sanitize_response_format_payload

logger = logging.getLogger("cognitive_needs.openai")
tracer = trace.get_tracer(__name__)
USER_FRIENDLY_TIMEOUT_SECONDS: float = 60.0

ToolCallable = Callable[..., Any]
UsageDict: TypeAlias = dict[str, int]

_MISSING_API_KEY_ALERT_STATE_KEY = "system.openai.api_key_missing_alert"
_MISSING_API_KEY_ALERT_MESSAGE: tuple[str, str] = (
    "\U0001f511 OpenAI-API-Schlüssel fehlt. Bitte `OPENAI_API_KEY` in der Umgebung oder in den Streamlit-Secrets hinterlegen.",
    "\U0001f511 OpenAI API key missing. Please set `OPENAI_API_KEY` via environment variable or Streamlit secrets.",
)
_MISSING_API_KEY_RUNTIME_MESSAGE: tuple[str, str] = (
    "OpenAI-API-Schlüssel nicht konfiguriert. Setze OPENAI_API_KEY in der Umgebung oder in den Streamlit-Secrets.",
    "OpenAI API key not configured. Set OPENAI_API_KEY in the environment or Streamlit secrets.",
)

_REASONING_MODEL_PATTERN = re.compile(r"^o\d")
_MODELS_WITHOUT_TEMPERATURE: set[str] = set()
_MODELS_WITHOUT_REASONING: set[str] = set()


class ToolCallPayload(TypedDict, total=False):
    """Normalised representation of a tool invocation returned by the API."""

    id: str
    call_id: str
    type: str
    function: Mapping[str, Any] | None
    content: str | Sequence[Any] | None
    output: str | Sequence[Any] | None
    name: str | None


class ToolMessagePayload(TypedDict, total=False):
    """Tool execution payload that is appended to the message list."""

    role: str
    tool_call_id: str
    content: str


class FileSearchResult(TypedDict, total=False):
    """Subset of the metadata we persist from file-search results."""

    id: str
    chunk_id: str
    file_id: str
    text: str
    metadata: Mapping[str, Any] | None


FileSearchKey = tuple[str, str, str]


@dataclass(frozen=True)
class ResponsesRequest:
    """Payload prepared for a single OpenAI API invocation."""

    payload: dict[str, Any]
    model: str | None
    tool_specs: list[dict[str, Any]]
    tool_functions: Mapping[str, ToolCallable]
    candidate_models: list[str]
    api_mode_override: str | None = None


@dataclass
class RetryState:
    """Mutable containers that survive individual retry attempts."""

    accumulated_usage: UsageDict = field(default_factory=dict)
    last_tool_calls: list[ToolCallPayload] = field(default_factory=list)
    file_search_results: list[FileSearchResult] = field(default_factory=list)
    seen_file_search: set[FileSearchKey] = field(default_factory=set)


@dataclass
class ChatFallbackContext:
    """Book-keeping helper that tracks fallback models during retries."""

    candidates: list[str]
    attempted: set[str] = field(default_factory=set)

    def initial_model(self) -> str:
        if not self.candidates:
            raise RuntimeError("No model candidates resolved for request")
        return self.candidates[0]

    def register_failure(self, failed_model: str) -> str | None:
        self.attempted.add(failed_model)
        for candidate in self.candidates:
            if candidate not in self.attempted:
                return candidate
        return None


def build_fallback_context(model: str | None, candidates: Sequence[str]) -> ChatFallbackContext:
    """Return a fallback context with duplicate candidates removed."""

    unique: list[str] = []
    for candidate in [model, *candidates]:
        if not candidate:
            continue
        if candidate not in unique:
            unique.append(candidate)
    return ChatFallbackContext(unique)


def create_retry_state() -> RetryState:
    """Return a fresh :class:`RetryState` instance."""

    return RetryState()


def _normalise_model_name(model: str | None) -> str:
    if not model:
        return ""
    return model.strip().lower()


def _mark_model_without_temperature(model: str | None) -> None:
    normalized = _normalise_model_name(model)
    if normalized:
        _MODELS_WITHOUT_TEMPERATURE.add(normalized)


def _mark_model_without_reasoning(model: str | None) -> None:
    normalized = _normalise_model_name(model)
    if normalized:
        _MODELS_WITHOUT_REASONING.add(normalized)


def model_supports_reasoning(model: str | None) -> bool:
    normalized = _normalise_model_name(model)
    if not normalized:
        return False
    if normalized in _MODELS_WITHOUT_REASONING:
        return False
    if _REASONING_MODEL_PATTERN.match(normalized):
        return True
    return "reasoning" in normalized


def model_supports_temperature(model: str | None) -> bool:
    normalized = _normalise_model_name(model)
    if not normalized:
        return True
    if normalized in _MODELS_WITHOUT_TEMPERATURE:
        return False
    if model_supports_reasoning(model):
        return False
    return "reasoning" not in normalized


def _should_mark_model_unavailable(error: OpenAIError) -> bool:
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


def _prune_payload_for_api_mode(payload: Mapping[str, Any], api_mode: str) -> dict[str, Any]:
    cleaned = dict(payload)
    removed: list[str] = []

    for key in list(cleaned):
        if key.startswith("_"):
            removed.append(key)
            cleaned.pop(key, None)

    mode = api_mode if api_mode in {"chat", "responses"} else "chat"

    if mode == "chat":
        if "messages" not in cleaned:
            raw_input = cleaned.get("input")
            if isinstance(raw_input, Sequence):
                cleaned["messages"] = raw_input
        for invalid_field in ("input", "text", "previous_response_id"):
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


class OpenAIClient:
    """Wrapper around the OpenAI SDK with retry/backoff helpers."""

    def __init__(self) -> None:
        self._client: OpenAI | None = None
        self._lock = Lock()

    def _show_missing_api_key_alert(self) -> None:
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

    def get_client(self) -> OpenAI:
        with self._lock:
            if self._client is None:
                key = OPENAI_API_KEY
                if not key:
                    self._show_missing_api_key_alert()
                    raise RuntimeError(resolve_message(_MISSING_API_KEY_RUNTIME_MESSAGE))
                base = OPENAI_BASE_URL or None
                init_kwargs: dict[str, Any] = {
                    "api_key": key,
                    "base_url": base,
                    "timeout": OPENAI_REQUEST_TIMEOUT,
                }
                organisation = (
                    OPENAI_ORGANIZATION.strip() if isinstance(OPENAI_ORGANIZATION, str) else OPENAI_ORGANIZATION
                )
                if organisation:
                    init_kwargs["organization"] = organisation
                project = OPENAI_PROJECT.strip() if isinstance(OPENAI_PROJECT, str) else OPENAI_PROJECT
                if project:
                    init_kwargs["project"] = project
                self._client = OpenAI(**init_kwargs)
            return self._client

    def _create_response_with_timeout(self, payload: dict[str, Any], *, api_mode: str) -> Any:
        request_kwargs = dict(payload)
        mode_override = request_kwargs.pop("_api_mode", None)
        raw_timeout = request_kwargs.pop("timeout", OPENAI_REQUEST_TIMEOUT)
        try:
            timeout_value = float(raw_timeout)
        except (TypeError, ValueError):  # pragma: no cover - defensive parsing
            timeout_value = float(OPENAI_REQUEST_TIMEOUT)
        timeout = min(timeout_value, USER_FRIENDLY_TIMEOUT_SECONDS)
        response_format_payload = request_kwargs.get("response_format")
        if isinstance(response_format_payload, Mapping):
            request_kwargs["response_format"] = sanitize_response_format_payload(response_format_payload)
        mode = mode_override or api_mode
        cleaned_payload = _prune_payload_for_api_mode(request_kwargs, mode)
        if mode != "chat":
            logger.debug("Routing non-chat mode '%s' through chat completions backend", mode)
        return self.get_client().chat.completions.create(timeout=timeout, **cleaned_payload)

    def _execute_once(
        self,
        payload: dict[str, Any],
        model: str | None,
        *,
        api_mode: str,
        on_known_error: Callable[[OpenAIError, str], None] | None = None,
    ) -> Any:
        with tracer.start_as_current_span("openai.execute_response") as span:
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
                return self._create_response_with_timeout(payload, api_mode=api_mode)
            except BadRequestError as err:
                span.record_exception(err)
                if on_known_error is not None:
                    on_known_error(err, api_mode=api_mode)
                if "temperature" in payload and _is_temperature_unsupported_error(err):
                    span.add_event("retry_without_temperature")
                    _mark_model_without_temperature(model)
                    payload.pop("temperature", None)
                    return self._create_response_with_timeout(payload, api_mode=api_mode)
                if "reasoning" in payload and _is_reasoning_unsupported_error(err):
                    span.add_event("retry_without_reasoning")
                    _mark_model_without_reasoning(model)
                    payload.pop("reasoning", None)
                    return self._create_response_with_timeout(payload, api_mode=api_mode)
                if model and _should_mark_model_unavailable(err):
                    mark_model_unavailable(model)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                raise
            except OpenAIError as err:
                span.record_exception(err)
                if on_known_error is not None:
                    on_known_error(err, api_mode=api_mode)
                if model and _should_mark_model_unavailable(err):
                    mark_model_unavailable(model)
                span.set_status(Status(StatusCode.ERROR, str(err)))
                raise

    def execute_request(
        self,
        payload: dict[str, Any],
        model: str | None,
        *,
        api_mode: str,
        giveup: Callable[[Exception], bool] | None = None,
        on_giveup: Callable[[Any], None] | None = None,
        on_known_error: Callable[[OpenAIError, str], None] | None = None,
    ) -> Any:
        def _should_give_up(exc: Exception) -> bool:
            return isinstance(exc, BadRequestError) or (giveup(exc) if giveup else False)

        @retry_with_backoff(giveup=_should_give_up, on_giveup=on_giveup)
        def _run() -> Any:
            return self._execute_once(dict(payload), model, api_mode=api_mode, on_known_error=on_known_error)

        return _run()


def _message_indicates_parameter_unsupported(message: str, parameter: str) -> bool:
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
    if not isinstance(value, str):
        return False
    lowered_value = value.strip().lower()
    return lowered_value == parameter or lowered_value.endswith(f".{parameter}")


def _iter_error_payloads(error: OpenAIError) -> Sequence[Mapping[str, Any]]:
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
    return _is_parameter_unsupported_error(error, "temperature")


def _is_reasoning_unsupported_error(error: OpenAIError) -> bool:
    return _is_parameter_unsupported_error(error, "reasoning")


__all__ = [
    "ToolCallPayload",
    "ToolMessagePayload",
    "UsageDict",
    "FileSearchResult",
    "FileSearchKey",
    "ResponsesRequest",
    "RetryState",
    "ChatFallbackContext",
    "build_fallback_context",
    "create_retry_state",
    "OpenAIClient",
    "model_supports_reasoning",
    "model_supports_temperature",
    "_is_reasoning_unsupported_error",
    "_is_temperature_unsupported_error",
]
