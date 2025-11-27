"""Payload construction helpers for the OpenAI Chat and Responses APIs."""

from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Final, Mapping, Optional, Sequence, cast

import streamlit as st

import config as app_config
from config import APIMode, OPENAI_REQUEST_TIMEOUT, REASONING_EFFORT, resolve_api_mode
from config.models import (
    ModelTask,
    get_first_available_model,
    get_model_candidates,
    get_reasoning_mode,
    select_model,
)
from constants.keys import StateKeys
from llm.cost_router import PromptCostEstimate, route_model_for_messages
from .client import ResponsesRequest, model_supports_reasoning, model_supports_temperature
from .schemas import SchemaFormatBundle, build_schema_format_bundle
from .tools import (
    _convert_tool_choice_to_function_call,
    _convert_tools_to_functions,
    _normalise_tool_choice_spec,
    _normalise_tool_spec,
)

logger = logging.getLogger("cognitive_needs.openai")

SUPPORTED_CHAT_PAYLOAD_FIELDS: Final[set[str]] = {
    "model",
    "messages",
    "temperature",
    "top_p",
    "max_tokens",
    "max_completion_tokens",
    "response_format",
    "tools",
    "tool_choice",
    "functions",
    "function_call",
    "stop",
    "n",
    "presence_penalty",
    "frequency_penalty",
    "logit_bias",
    "logprobs",
    "metadata",
    "stream",
    "stream_options",
    "user",
    "seed",
    "timeout",
    "extra_headers",
    "extra_query",
    "extra_body",
}


def _inject_json_hint(messages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Prepend a system hint asking the model to respond with JSON."""

    hint = {
        "role": "system",
        "content": "Respond with a JSON object following the requested structure.",
    }
    return [hint, *[dict(message) for message in messages]]


def _clean_response_format_for_chat(response_format: Mapping[str, Any]) -> dict[str, Any]:
    """Return a Chat-friendly ``response_format`` without Responses-only fields."""

    cleaned: dict[str, Any] = dict(deepcopy(response_format))
    removed_fields: list[str] = []

    if "strict" in cleaned:
        cleaned.pop("strict", None)
        removed_fields.append("response_format.strict")

    json_schema_block = cleaned.get("json_schema")
    if isinstance(json_schema_block, Mapping) and "strict" in json_schema_block:
        json_schema_block = dict(json_schema_block)
        json_schema_block.pop("strict", None)
        cleaned["json_schema"] = json_schema_block
        removed_fields.append("response_format.json_schema.strict")

    if removed_fields:
        logger.debug(
            "Cleaning Responses-only fields from chat response_format: %s",
            ", ".join(removed_fields),
        )

    return cleaned


def _strip_unsupported_chat_fields(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove unexpected fields from a Chat Completions payload."""

    unexpected = sorted(set(payload) - SUPPORTED_CHAT_PAYLOAD_FIELDS)
    if unexpected:
        for field in unexpected:
            payload.pop(field, None)
        logger.debug(
            "Removed unsupported fields from Chat Completions fallback payload: %s",
            ", ".join(unexpected),
        )

    return payload


def _convert_responses_payload_to_chat(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    """Translate a Responses payload to a Chat Completions payload when possible."""

    raw_messages = payload.get("input") or payload.get("messages")
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
    if not isinstance(max_tokens, int):
        max_tokens = cast(Optional[int], payload.get("max_completion_tokens"))
    if max_tokens is not None:
        chat_payload["max_tokens"] = max_tokens
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
                chat_payload["response_format"] = _clean_response_format_for_chat(schema_bundle.chat_response_format)

    cleaned_payload = _strip_unsupported_chat_fields(chat_payload)
    logger.debug(
        "Prepared chat fallback payload keys: %s",
        ", ".join(sorted(cleaned_payload)),
    )

    return cleaned_payload


def _build_chat_fallback_payload(
    payload: Mapping[str, Any],
    messages: Sequence[Mapping[str, Any]],
    schema_bundle: SchemaFormatBundle | None,
) -> dict[str, Any]:
    """Construct a Chat Completions payload mirroring ``payload``."""

    converted = _convert_responses_payload_to_chat(payload)
    if converted is not None:
        if schema_bundle is not None and schema_bundle.strict:
            converted["messages"] = _inject_json_hint(converted.get("messages", []))
        return converted

    message_payload: list[dict[str, Any]] = [dict(message) for message in messages]
    if schema_bundle is not None and schema_bundle.strict:
        message_payload = _inject_json_hint(message_payload)

    chat_payload: dict[str, Any] = {
        "model": payload.get("model"),
        "messages": message_payload,
        "timeout": payload.get("timeout", OPENAI_REQUEST_TIMEOUT),
    }

    if "temperature" in payload and model_supports_temperature(payload.get("model")):
        chat_payload["temperature"] = payload.get("temperature")

    if "max_output_tokens" in payload:
        chat_payload["max_completion_tokens"] = payload.get("max_output_tokens")

    response_format = payload.get("response_format")
    if isinstance(response_format, Mapping):
        chat_payload["response_format"] = _clean_response_format_for_chat(response_format)
    elif schema_bundle is not None:
        chat_payload["response_format"] = _clean_response_format_for_chat(schema_bundle.chat_response_format)

    if "strict" in chat_payload:
        chat_payload.pop("strict", None)
        logger.debug("Removed top-level strict flag from chat fallback payload.")

    return _strip_unsupported_chat_fields(chat_payload)


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
    api_mode: APIMode
    api_mode_override: str | None = None

    @property
    def use_classic_api(self) -> bool:
        return self.api_mode.is_classic or self.force_classic_for_tools


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
            payload["response_format"] = _clean_response_format_for_chat(
                deepcopy(self.context.schema_bundle.chat_response_format)
            )
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
            format_payload = deepcopy(self.context.schema_bundle.responses_format)
            format_payload.setdefault("name", self.context.schema_bundle.name)
            if isinstance(format_payload.get("json_schema"), Mapping):
                format_payload["json_schema"].setdefault("name", self.context.schema_bundle.name)
            format_payload.setdefault("schema", deepcopy(self.context.schema_bundle.schema))
            text_config["format"] = format_payload
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
    api_mode: APIMode | str | bool | None = None,
    use_response_format: bool = True,
) -> ResponsesRequest:
    """Assemble the payload for the configured OpenAI API."""

    active_mode = resolve_api_mode(api_mode)
    use_classic_api = active_mode.is_classic

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

    effort_value = reasoning_effort.strip().lower() if isinstance(reasoning_effort, str) else None
    mode = get_reasoning_mode()
    if mode == "quick" and effort_value not in {"minimal", "low"}:
        reasoning_effort = "low"
    elif mode == "precise" and effort_value in {None, "minimal", "low"}:
        reasoning_effort = "high"

    candidate_models = get_model_candidates(selected_task, override=candidate_override)
    if model and model not in candidate_models:
        candidate_models = [model, *candidate_models]
    elif not candidate_models and model:
        candidate_models = [model]

    raw_tools = [dict(tool) for tool in (tools or [])]
    tool_map = dict(tool_functions or {})
    requested_tools = bool(raw_tools or tool_map)
    analysis_tools_enabled = include_analysis_tools and (
        use_classic_api or requested_tools or app_config.RESPONSES_ALLOW_TOOLS
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
    if json_schema is not None and not use_response_format:
        messages_payload = _inject_json_hint(messages_payload)
    normalised_tool_choice = _normalise_tool_choice_spec(tool_choice) if tool_choice is not None else None

    schema_bundle: SchemaFormatBundle | None = None
    if json_schema is not None and use_response_format:
        schema_bundle = build_schema_format_bundle(json_schema)

    force_classic_for_tools = bool(combined_tools and not (use_classic_api or app_config.RESPONSES_ALLOW_TOOLS))
    api_mode_override: str | None = "chat" if force_classic_for_tools else active_mode.value

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
        api_mode=active_mode,
        api_mode_override=api_mode_override,
    )

    builder: _BasePayloadBuilder
    if context.use_classic_api:
        builder = ChatPayloadBuilder(context)
    else:
        builder = ResponsesPayloadBuilder(context)

    return builder.build()
