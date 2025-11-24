"""Central accessors for NeedAnalysis schema artifacts.

The helpers in this module provide a single entry point for consumers that need
the NeedAnalysis JSON schema, ensuring downstream logic, prompts, and exports
all share the same definition. The builder is sourced from the Pydantic model
and cached, with a disk-based fallback to keep legacy uses stable.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Collection, Iterable, Mapping

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema" / "need_analysis.schema.json"


def _load_schema_from_disk() -> dict[str, Any]:
    """Return the NeedAnalysis JSON schema from disk, or an empty mapping."""

    try:
        return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.error("NeedAnalysis schema file missing at %s", _SCHEMA_PATH)
    except json.JSONDecodeError:
        logger.exception("NeedAnalysis schema contains invalid JSON at %s", _SCHEMA_PATH)
    return {}


def _trim_sections(schema: Mapping[str, Any], sections: Collection[str]) -> dict[str, Any]:
    """Return ``schema`` limited to the requested top-level ``sections``."""

    properties = schema.get("properties")
    required = schema.get("required")

    selected_properties: dict[str, Any] = {}
    if isinstance(properties, Mapping):
        selected_properties = {
            name: value for name, value in properties.items() if isinstance(name, str) and name in sections
        }

    selected_required: list[str] = []
    if isinstance(required, Collection):
        selected_required = [name for name in required if isinstance(name, str) and name in sections]

    trimmed = dict(schema)
    trimmed["properties"] = selected_properties
    trimmed["required"] = selected_required
    return trimmed


@lru_cache(maxsize=8)
def _load_schema_cached(section_tuple: tuple[str, ...] | None) -> dict[str, Any]:
    """Return the canonical NeedAnalysis JSON schema with optional section limiting."""

    try:
        from core.schema import build_need_analysis_responses_schema

        schema = build_need_analysis_responses_schema(sections=section_tuple)
        return schema
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("Falling back to disk schema after builder failure: %s", exc)

    schema = _load_schema_from_disk()
    if section_tuple:
        return _trim_sections(schema, section_tuple)
    return schema


def load_need_analysis_schema(*, sections: Collection[str] | None = None) -> dict[str, Any]:
    """Return the canonical NeedAnalysis JSON schema with optional section limiting."""

    section_tuple = tuple(sections) if sections else None
    return _load_schema_cached(section_tuple)


def _flatten_schema_fields(schema: Mapping[str, Any], prefix: str = "") -> list[str]:
    """Return dotted field paths from ``schema`` preserving property order."""

    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        return []

    fields: list[str] = []
    for name, subschema in properties.items():
        path = f"{prefix}{name}" if not prefix else f"{prefix}.{name}"
        nested_props = subschema.get("properties") if isinstance(subschema, Mapping) else None
        type_marker = subschema.get("type") if isinstance(subschema, Mapping) else None
        types: set[str] = set()
        if isinstance(type_marker, str):
            types.add(type_marker)
        elif isinstance(type_marker, Iterable):
            types.update(str(entry) for entry in type_marker)

        if nested_props and ("object" in types or not types):
            fields.extend(_flatten_schema_fields(subschema, prefix=path))
        else:
            fields.append(path)
    return fields


def iter_need_analysis_field_paths(*, sections: Collection[str] | None = None) -> tuple[str, ...]:
    """Return dotted NeedAnalysis field paths derived from the JSON schema."""

    schema = load_need_analysis_schema(sections=sections)
    return tuple(_flatten_schema_fields(schema))


__all__ = ["iter_need_analysis_field_paths", "load_need_analysis_schema"]
