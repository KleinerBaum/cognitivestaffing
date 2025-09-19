"""OpenAI API client and chat helpers.

This module isolates low-level interactions with the OpenAI Responses API.
It provides a :func:`call_chat_api` helper that also executes any requested
function tools and feeds the results back to the model, effectively acting as
"mini agent" loop.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Sequence

import backoff
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

from config import (
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    REASONING_EFFORT,
    ModelTask,
    get_model_for,
)
from constants.keys import StateKeys

logger = logging.getLogger("cognitive_needs.openai")

# Global client instance (monkeypatchable in tests)
client: OpenAI | None = None


_REASONING_MODEL_PATTERN = re.compile(r"^o\d")
_MODELS_WITHOUT_TEMPERATURE: set[str] = set()


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


def model_supports_reasoning(model: Optional[str]) -> bool:
    """Return ``True`` if ``model`` accepts a reasoning payload.

    OpenAI exposes the explicit ``reasoning`` parameter only on the dedicated
    reasoning-capable families (``o1`` variants and names containing the
    ``reasoning`` suffix). We heuristically detect those models to avoid
    sending the parameter to regular chat models that would reject it.
    """

    if not model:
        return False
    normalized = model.strip().lower()
    if not normalized:
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


def _is_temperature_unsupported_error(error: OpenAIError) -> bool:
    """Return ``True`` if ``error`` indicates the model rejected ``temperature``."""

    message = getattr(error, "message", str(error)).lower()
    return "unsupported parameter" in message and "temperature" in message


def _execute_response(payload: Dict[str, Any], model: Optional[str]) -> Any:
    """Send ``payload`` to the Responses API and retry without temperature if needed."""

    try:
        return get_client().responses.create(**payload)
    except BadRequestError as err:
        if "temperature" in payload and _is_temperature_unsupported_error(err):
            _mark_model_without_temperature(model)
            payload.pop("temperature", None)
            cleaned_payload = dict(payload)
            return get_client().responses.create(**cleaned_payload)
        raise


@dataclass
class ChatCallResult:
    """Unified return type for :func:`call_chat_api`.

    Attributes:
        content: Text content returned by the model, if any.
        tool_calls: List of tool call payloads.
        usage: Token usage information.
    """

    content: Optional[str]
    tool_calls: list[dict]
    usage: dict


def get_client() -> OpenAI:
    """Return a configured OpenAI client."""

    global client
    if client is None:
        key = OPENAI_API_KEY
        if not key:
            raise RuntimeError(
                "OpenAI API key not configured. Set OPENAI_API_KEY in the environment or Streamlit secrets."
            )
        base = OPENAI_BASE_URL or None
        client = OpenAI(api_key=key, base_url=base)
    return client


def _handle_openai_error(error: OpenAIError) -> None:
    """Raise a user-friendly ``RuntimeError`` for OpenAI failures."""

    if isinstance(error, AuthenticationError):
        user_msg = "OpenAI API key invalid or quota exceeded."
    elif isinstance(error, RateLimitError):
        user_msg = "OpenAI API rate limit exceeded. Please retry later."
    elif isinstance(error, (APIConnectionError, APITimeoutError)):
        user_msg = "Network error communicating with OpenAI. Please check your connection and retry."
    elif (
        isinstance(error, BadRequestError)
        or getattr(error, "type", "") == "invalid_request_error"
    ):
        detail = getattr(error, "message", str(error))
        log_msg = f"OpenAI invalid request: {detail}"
        user_msg = "❌ An internal error occurred while processing your request. (The app made an invalid request to the AI model.)"
    elif isinstance(error, APIError):
        detail = getattr(error, "message", str(error))
        user_msg = f"OpenAI API error: {detail}"
    else:
        user_msg = f"Unexpected OpenAI error: {error}"

    log_msg = locals().get("log_msg", user_msg)
    logger.error(log_msg, exc_info=error)
    try:  # pragma: no cover - Streamlit may not be initialised in tests
        st.error(user_msg)
    except Exception:  # noqa: BLE001
        pass
    raise RuntimeError(user_msg) from error


def _on_api_giveup(details: Any) -> None:
    """Handle a final API error after retries have been exhausted."""

    err = details.get("exception")
    if isinstance(err, OpenAIError):  # pragma: no cover - defensive
        _handle_openai_error(err)
    raise err  # pragma: no cover - re-raise unexpected errors


@backoff.on_exception(
    backoff.expo,
    (OpenAIError,),
    max_tries=3,
    jitter=backoff.full_jitter,
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
    extra: Optional[dict] = None,
) -> ChatCallResult:
    """Call the OpenAI Responses API and return a :class:`ChatCallResult`.

    If the model requests a function tool, the function is executed locally and
    the result appended to the message list before the API call is retried. This
    mirrors OpenAI's tool-calling flow while keeping the logic transparent and
    testable.
    """

    from core import analysis_tools

    if model is None:
        model = get_model_for(ModelTask.DEFAULT)
    if reasoning_effort is None:
        reasoning_effort = st.session_state.get("reasoning_effort", REASONING_EFFORT)

    base_tools, base_funcs = analysis_tools.build_analysis_tools()
    tools = (tools or []) + base_tools
    tool_functions = {**base_funcs, **(tool_functions or {})}

    payload: Dict[str, Any] = {
        "model": model,
        "input": messages,
    }
    if temperature is not None and model_supports_temperature(model):
        payload["temperature"] = temperature
    if model_supports_reasoning(model):
        payload["reasoning"] = {"effort": reasoning_effort}
    if max_tokens is not None:
        payload["max_output_tokens"] = max_tokens
    if json_schema is not None:
        payload["text"] = {"format": {"type": "json_schema", **json_schema}}
    if tools:
        payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
    if extra:
        payload.update(extra)

    def _to_mapping(item: Any) -> dict[str, Any] | None:
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

    def _extract_output_text(response_obj: Any) -> Optional[str]:
        text = getattr(response_obj, "output_text", None)
        if text:
            return text
        chunks: list[str] = []
        for raw_item in getattr(response_obj, "output", []) or []:
            item_dict = _to_mapping(raw_item)
            if not item_dict:
                continue
            item_type = item_dict.get("type")
            contents = item_dict.get("content")
            if isinstance(contents, Sequence) and not isinstance(
                contents, (str, bytes)
            ):
                iterable = contents
            else:
                iterable = []
            if item_type == "message" and iterable:
                for raw_content in iterable:
                    content_dict = _to_mapping(raw_content)
                    if not content_dict:
                        continue
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
                    text_value = content_dict.get("text")
                    if text_value:
                        chunks.append(str(text_value))
        if chunks:
            return "\n".join(chunk for chunk in chunks if chunk)
        return text

    response = _execute_response(payload, model)

    content = _extract_output_text(response)

    tool_calls: list[dict] = []
    for item in getattr(response, "output", []) or []:
        data = _to_mapping(item)
        if not data:
            continue
        typ = data.get("type")
        if typ and "call" in str(typ):
            call_data = dict(data)
            fn = call_data.get("function")
            if fn is None:
                name = call_data.get("name")
                arg_str = call_data.get("arguments")
                call_data = {
                    **call_data,
                    "function": {"name": name, "arguments": arg_str},
                }
            tool_calls.append(call_data)

    usage_obj = getattr(response, "usage", {}) or {}
    if usage_obj and not isinstance(usage_obj, dict):
        usage: dict = getattr(
            usage_obj, "model_dump", getattr(usage_obj, "dict", lambda: {})
        )()
    else:
        usage = usage_obj if isinstance(usage_obj, dict) else {}

    executed = False
    if tool_calls and tool_functions:
        messages_list = list(messages)
        for call in tool_calls:
            func_info = call.get("function", {})
            name = func_info.get("name")
            if not name or name not in tool_functions:
                continue
            args_raw = func_info.get("arguments", "{}") or "{}"
            try:
                parsed: Any = json.loads(args_raw)
                args: dict[str, Any] = parsed if isinstance(parsed, dict) else {}
            except Exception:  # pragma: no cover - defensive
                args = {}
            result = tool_functions[name](**args)
            messages_list.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id", name),
                    "content": json.dumps(result),
                }
            )
            executed = True

        if executed:
            payload["input"] = messages_list
            payload.pop("tool_choice", None)
            response = _execute_response(payload, model)
            content = _extract_output_text(response)
            extra_calls: list[dict] = []
            for item in getattr(response, "output", []) or []:
                data = _to_mapping(item)
                if not data:
                    continue
                typ = data.get("type")
                if typ and "call" in str(typ):
                    call_data = dict(data)
                    fn = call_data.get("function")
                    if fn is None:
                        name = call_data.get("name")
                        arg_str = call_data.get("arguments")
                        call_data = {
                            **call_data,
                            "function": {"name": name, "arguments": arg_str},
                        }
                    extra_calls.append(call_data)
            tool_calls.extend(extra_calls)
            usage_obj = getattr(response, "usage", {}) or {}
            if usage_obj and not isinstance(usage_obj, dict):
                usage_extra: dict = getattr(
                    usage_obj, "model_dump", getattr(usage_obj, "dict", lambda: {})
                )()
            else:
                usage_extra = usage_obj if isinstance(usage_obj, dict) else {}
            for key in ("input_tokens", "output_tokens"):
                usage[key] = usage.get(key, 0) + usage_extra.get(key, 0)

    if StateKeys.USAGE in st.session_state:
        st.session_state[StateKeys.USAGE]["input_tokens"] += usage.get(
            "input_tokens", 0
        )
        st.session_state[StateKeys.USAGE]["output_tokens"] += usage.get(
            "output_tokens", 0
        )

    return ChatCallResult(content, tool_calls, usage)


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
    "get_client",
    "client",
    "model_supports_reasoning",
    "model_supports_temperature",
    "_chat_content",
]
