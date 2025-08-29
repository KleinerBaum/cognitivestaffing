"""Utilities for constructing OpenAI tool specifications.

These helpers complement the static tool definitions in
:mod:`core.analysis_tools`. ``build_extraction_tool`` creates a single
function-style tool spec on the fly, primarily used for strict JSON
extraction tasks.
"""

from __future__ import annotations


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

    params = {**schema, "additionalProperties": bool(allow_extra)}
    return [
        {
            "type": "function",
            "name": name,
            "description": "Return structured profile data that fits the schema exactly.",
            "parameters": params,
            "strict": not allow_extra,
        }
    ]


__all__ = ["build_extraction_tool"]
