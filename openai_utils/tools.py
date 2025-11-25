"""Utilities for constructing OpenAI tool specifications.

These helpers complement the static tool definitions in
:mod:`core.analysis_tools`. ``build_extraction_tool`` creates a single
function-style tool spec on the fly, primarily used for strict JSON
extraction tasks.
"""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from copy import deepcopy
from typing import Any, cast

from prompts import prompt_registry
from core.schema_guard import guard_no_additional_properties
from .client import ToolCallPayload, ToolMessagePayload


def _prepare_schema(obj: dict[str, Any], *, require_all: bool) -> dict[str, Any]:
    """Inject ``required`` arrays and nullable types into ``obj`` in-place."""

    def _walk(node: Any) -> None:
        if not isinstance(node, dict):
            return

        props = node.get("properties")
        if isinstance(props, dict):
            if require_all and "required" not in node:
                node["required"] = list(props.keys())
            for sub in props.values():
                if isinstance(sub, dict):
                    _make_nullable(sub)
                    _walk(sub)

        items = node.get("items")
        if isinstance(items, dict):
            _walk(items)

    def _make_nullable(field: dict[str, Any]) -> None:
        t = field.get("type")
        if isinstance(t, str):
            if t not in {"object", "array"}:
                field["type"] = [t, "null"]
        elif isinstance(t, list):
            if "null" not in t:
                field["type"] = [*t, "null"]

    _walk(obj)
    return obj


def _is_object_schema(node: Mapping[str, Any]) -> bool:
    """Return ``True`` when ``node`` represents a JSON object schema."""

    type_hint = node.get("type")
    if type_hint is None:
        return isinstance(node.get("properties"), Mapping)
    if isinstance(type_hint, str):
        return type_hint == "object"
    if isinstance(type_hint, Iterable):
        return "object" in type_hint
    return False


def _collect_schema_fields(schema: Mapping[str, Any], *, limit: int = 8) -> list[str]:
    """Collect representative dot-paths from ``schema`` to surface in docs."""

    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        return []

    collected: list[str] = []
    queue: deque[tuple[tuple[str, ...], Mapping[str, Any]]] = deque()
    queue.append(((), properties))

    while queue and len(collected) < limit:
        path, props = queue.popleft()
        for key, value in props.items():
            new_path = (*path, key)
            if isinstance(value, Mapping):
                child_props = value.get("properties")
                if _is_object_schema(value) and isinstance(child_props, Mapping) and child_props:
                    queue.append((new_path, child_props))
                    if len(collected) >= limit:
                        break
                    continue
            collected.append(".".join(new_path))
            if len(collected) >= limit:
                break

    return collected


def build_extraction_tool(
    name: str,
    schema: dict[str, Any],
    *,
    allow_extra: bool = False,
    require_all_fields: bool = True,
    description: str | None = None,
) -> list[dict[str, Any]]:
    """Return an OpenAI tool spec for structured extraction.

    Args:
        name: Name of the tool for the model.
        schema: JSON schema dict that defines the expected output.
        allow_extra: Whether additional properties are allowed in the output.
        require_all_fields: When ``True`` every object property is marked as
            required. Disable to allow the model to omit optional fields.

    Returns:
        A list containing a single tool specification dictionary.
    """

    params = guard_no_additional_properties(schema)
    _prepare_schema(params, require_all=require_all_fields)
    params["additionalProperties"] = bool(allow_extra)

    if description is None:
        fields = _collect_schema_fields(schema)
        if fields:
            fields_text = ", ".join(fields)
            description = prompt_registry.format(
                "openai_utils.tools.schema_description_with_fields",
                fields=fields_text,
            )
        else:
            description = prompt_registry.get("openai_utils.tools.schema_description_base")

    return [
        {
            "name": name,
            "description": description,
            "parameters": params,
        }
    ]


def build_function_tools(
    specs: Mapping[str, Mapping[str, Any]],
    *,
    callables: Mapping[str, Callable[..., Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Callable[..., Any]]]:
    """Return OpenAI tool specs and callable mapping for ``call_chat_api``.

    Args:
        specs: Mapping from tool name to a function specification. Each
            specification should contain the JSON schema under ``parameters``
            and optional metadata accepted by the OpenAI API (for example a
            ``description`` flag). The helper copies the
            specification to avoid mutating the caller's data.
        callables: Optional mapping with Python callables that implement the
            tool behaviour. When omitted, the helper will fall back to
            resolving a ``callable`` key present in the individual tool specs.

    Returns:
        Tuple containing the list of OpenAI tool specifications and a mapping
        from tool name to the callable that should be invoked when the model
        selects the tool.

    Raises:
        ValueError: If a specification does not define ``parameters``.
        TypeError: If ``parameters`` is not a mapping or the provided callable
            is not callable.
    """

    tools: list[dict[str, Any]] = []
    functions: dict[str, Callable[..., Any]] = {}

    for name, spec in specs.items():
        if not isinstance(spec, Mapping):
            raise TypeError(f"Tool specification for '{name}' must be a mapping")

        function_payload: dict[str, Any] = {"name": name}
        callable_obj: Callable[..., Any] | None = None

        for key, value in spec.items():
            if key == "callable":
                if value is not None and not callable(value):
                    raise TypeError(f"Callable for tool '{name}' must be callable")
                if value is not None:
                    callable_obj = cast(Callable[..., Any], value)
                else:
                    callable_obj = None

                continue
            function_payload[key] = deepcopy(value)

        if "parameters" not in function_payload:
            raise ValueError(f"Tool '{name}' must define a 'parameters' schema")

        parameters = function_payload["parameters"]
        if not isinstance(parameters, Mapping):
            raise TypeError(f"Tool '{name}' expects 'parameters' to be a mapping, got {type(parameters)!r}")

        tools.append(function_payload)

        if callables and name in callables:
            callable_obj = callables[name]

        if callable_obj is not None:
            if not callable(callable_obj):
                raise TypeError(f"Callable for tool '{name}' must be callable")
            functions[name] = callable_obj

    return tools, functions


def _serialise_tool_payload(value: Any) -> str | None:
    """Return ``value`` as a JSON string when possible."""

    if value is None:
        return None
    if isinstance(value, str):
        return value

    try:
        return json.dumps(value)
    except Exception:  # pragma: no cover - defensive
        return None


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
            continue

        functions.append(function_payload)
    return functions


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


def build_file_search_tool(
    vector_store_ids: Sequence[str] | str,
    *,
    name: str = "file_search",
) -> dict[str, Any]:
    """Return an OpenAI tool spec for the ``file_search`` tool.

    Args:
        vector_store_ids: Single vector store identifier or sequence of
            identifiers to associate with the tool.
        name: Optional name exposed to the model. Defaults to ``"file_search"``
            to mirror OpenAI's native tool label.

    Returns:
        A dictionary matching the OpenAI ``file_search`` tool schema with a
        guaranteed ``name`` attribute for compatibility with the Chat
        Completions API.
    """

    if isinstance(vector_store_ids, str):
        raw_ids = [vector_store_ids]
    else:
        raw_ids = list(vector_store_ids)

    cleaned_ids = [str(identifier).strip() for identifier in raw_ids if str(identifier).strip()]
    if not cleaned_ids:
        raise ValueError("At least one vector store ID must be provided.")

    payload: dict[str, Any] = {
        "type": "file_search",
        "name": name,
        "vector_store_ids": cleaned_ids,
        "file_search": {"vector_store_ids": cleaned_ids},
    }
    return payload


__all__ = ["build_extraction_tool", "build_function_tools", "build_file_search_tool"]
