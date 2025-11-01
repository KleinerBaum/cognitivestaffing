"""Utilities for constructing OpenAI tool specifications.

These helpers complement the static tool definitions in
:mod:`core.analysis_tools`. ``build_extraction_tool`` creates a single
function-style tool spec on the fly, primarily used for strict JSON
extraction tasks.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable, Mapping, Sequence
from copy import deepcopy
from typing import Any, cast

from prompts import prompt_registry


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

    params = deepcopy(schema)
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
