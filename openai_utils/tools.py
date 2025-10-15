"""Utilities for constructing OpenAI tool specifications.

These helpers complement the static tool definitions in
:mod:`core.analysis_tools`. ``build_extraction_tool`` creates a single
function-style tool spec on the fly, primarily used for strict JSON
extraction tasks.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any


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


def build_extraction_tool(
    name: str,
    schema: dict,
    *,
    allow_extra: bool = False,
    require_all_fields: bool = True,
) -> list[dict]:
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
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": "Return structured profile data that fits the schema exactly.",
                "parameters": params,
                "strict": not allow_extra,
            },
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
            ``description`` or ``strict`` flag). The helper copies the
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

        function_payload: dict[str, Any] = {}
        callable_obj: Callable[..., Any] | None = None

        for key, value in spec.items():
            if key == "callable":
                if value is not None and not callable(value):
                    raise TypeError(f"Callable for tool '{name}' must be callable")
                callable_obj = value  # type: ignore[assignment]
                continue
            function_payload[key] = deepcopy(value)

        function_payload["name"] = name

        if "parameters" not in function_payload:
            raise ValueError(f"Tool '{name}' must define a 'parameters' schema")

        parameters = function_payload["parameters"]
        if not isinstance(parameters, Mapping):
            raise TypeError(f"Tool '{name}' expects 'parameters' to be a mapping, got {type(parameters)!r}")

        tools.append({"type": "function", "function": function_payload})

        if callables and name in callables:
            callable_obj = callables[name]

        if callable_obj is not None:
            if not callable(callable_obj):
                raise TypeError(f"Callable for tool '{name}' must be callable")
            functions[name] = callable_obj

    return tools, functions


__all__ = ["build_extraction_tool", "build_function_tools"]
