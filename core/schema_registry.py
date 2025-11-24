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
from typing import Any, Collection, Mapping

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
            name: value
            for name, value in properties.items()
            if isinstance(name, str) and name in sections
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


__all__ = ["load_need_analysis_schema"]
