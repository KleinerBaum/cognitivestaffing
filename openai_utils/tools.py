"""Utilities for constructing OpenAI tool specifications.

These helpers complement the static tool definitions in
:mod:`core.analysis_tools`. ``build_extraction_tool`` creates a single
function-style tool spec on the fly, primarily used for strict JSON
extraction tasks.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _prepare_schema(obj: dict[str, Any]) -> dict[str, Any]:
    """Inject ``required`` arrays and nullable types into ``obj`` in-place."""

    def _walk(node: Any) -> None:
        if not isinstance(node, dict):
            return

        props = node.get("properties")
        if isinstance(props, dict):
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
    name: str, schema: dict, *, allow_extra: bool = False
) -> list[dict]:
    """Return an OpenAI tool spec for structured extraction.

    Args:
        name: Name of the tool for the model.
        schema: JSON schema dict that defines the expected output.
        allow_extra: Whether additional properties are allowed in the output.

    Returns:
        A list containing a single tool specification dictionary.
    """

    params = deepcopy(schema)
    _prepare_schema(params)
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


__all__ = ["build_extraction_tool"]
