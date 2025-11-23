"""Helpers for enforcing strict JSON schema object definitions."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


def guard_no_additional_properties(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Return ``schema`` with ``additionalProperties`` disabled for every object."""

    guarded = deepcopy(dict(schema))

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" or "properties" in node or "patternProperties" in node:
                node["additionalProperties"] = False
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(guarded)
    return guarded


__all__ = ["guard_no_additional_properties"]
