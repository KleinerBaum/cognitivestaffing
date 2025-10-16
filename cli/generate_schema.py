"""Utilities for regenerating persisted JSON schema files."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from models.need_analysis import NeedAnalysisProfile

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "need_analysis.schema.json"


def _expand_refs(schema: dict[str, Any]) -> dict[str, Any]:
    """Inline ``$ref`` pointers in ``schema`` using its ``$defs`` section."""

    definitions = deepcopy(schema.get("$defs", {}))

    def _expand(node: Any) -> Any:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str):
                if not ref.startswith("#/$defs/"):
                    msg = f"Unsupported $ref target: {ref}"
                    raise ValueError(msg)
                key = ref.rsplit("/", 1)[-1]
                if key not in definitions:
                    msg = f"Unresolved $ref: {ref}"
                    raise KeyError(msg)
                return _expand(deepcopy(definitions[key]))

            expanded: dict[str, Any] = {}
            for sub_key, sub_value in node.items():
                if sub_key == "$defs":
                    continue
                expanded[sub_key] = _expand(sub_value)
            return expanded

        if isinstance(node, list):
            return [_expand(item) for item in node]

        return node

    return _expand(schema)


def _collapse_nullable_types(node: dict[str, Any]) -> None:
    """Replace ``anyOf`` nullability markers with ``type`` lists in ``node``."""

    any_of = node.get("anyOf")
    if not isinstance(any_of, list):
        return

    types: list[str] = []
    metadata: dict[str, Any] = {}
    for option in any_of:
        if not isinstance(option, dict):
            continue
        opt_type = option.get("type")
        if isinstance(opt_type, str):
            if opt_type not in types:
                types.append(opt_type)
        for key, value in option.items():
            if key == "type":
                continue
            metadata[key] = value

    if not types:
        return

    node.pop("anyOf", None)
    node["type"] = types[0] if len(types) == 1 else types
    for key, value in metadata.items():
        node.setdefault(key, value)


def _normalise_schema(node: Any) -> None:
    """Recursively enforce required arrays and prune unused metadata."""

    if isinstance(node, dict):
        _collapse_nullable_types(node)

        for removable in ("title", "description", "default"):
            node.pop(removable, None)

        props = node.get("properties")
        if isinstance(props, dict):
            existing_required = node.get("required")
            if isinstance(existing_required, list):
                filtered_required = [prop for prop in existing_required if prop in props]
                if filtered_required:
                    node["required"] = filtered_required
                else:
                    node.pop("required", None)
            else:
                node.pop("required", None)

            for child in props.values():
                _normalise_schema(child)

        items = node.get("items")
        if isinstance(items, dict):
            _normalise_schema(items)
        elif isinstance(items, list):
            for child in items:
                _normalise_schema(child)

    elif isinstance(node, list):
        for item in node:
            _normalise_schema(item)


def generate_need_analysis_schema() -> dict[str, Any]:
    """Return the normalised Need Analysis JSON schema."""

    raw_schema = NeedAnalysisProfile.model_json_schema()
    expanded = _expand_refs(raw_schema)
    _normalise_schema(expanded)
    expanded.setdefault("$schema", "http://json-schema.org/draft-07/schema#")
    expanded.setdefault("title", NeedAnalysisProfile.__name__)
    expanded.setdefault("type", "object")
    return expanded


def write_need_analysis_schema(path: Path = SCHEMA_PATH) -> None:
    """Regenerate the persisted schema file on disk."""

    schema = generate_need_analysis_schema()
    path.write_text(json.dumps(schema, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover - CLI convenience
    write_need_analysis_schema()
