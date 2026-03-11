"""Central schema/model registry for versioned need-analysis contracts."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Collection, Iterable, Mapping
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel


logger = logging.getLogger(__name__)

SchemaVersion = Literal["v1", "v2"]
SchemaArtifact = Literal["need_analysis", "vacancy_extraction", "followups"]
AdapterPath = tuple[SchemaVersion, SchemaVersion]

_SCHEMA_PATH_V1 = Path(__file__).resolve().parent.parent / "schema" / "need_analysis.schema.json"
_SCHEMA_PATH_V2 = Path(__file__).resolve().parent.parent / "schema" / "need_analysis_v2.schema.json"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_need_analysis_v1_schema(*, sections: Collection[str] | None = None) -> dict[str, Any]:
    from core.schema import build_need_analysis_responses_schema

    section_tuple = tuple(sections) if sections else None
    return build_need_analysis_responses_schema(sections=section_tuple)


def _build_need_analysis_v2_schema(*, sections: Collection[str] | None = None) -> dict[str, Any]:
    schema = _load_json(_SCHEMA_PATH_V2)
    if sections:
        return _trim_sections(schema, sections)
    return schema


def _build_vacancy_extraction_schema(*, _version: SchemaVersion) -> dict[str, Any]:
    from schemas import VACANCY_EXTRACTION_SCHEMA

    return deepcopy(VACANCY_EXTRACTION_SCHEMA)


def _build_followups_schema(*, _version: SchemaVersion) -> dict[str, Any]:
    from schemas import FOLLOW_UPS_SCHEMA

    return deepcopy(FOLLOW_UPS_SCHEMA)


def _trim_sections(schema: Mapping[str, Any], sections: Collection[str]) -> dict[str, Any]:
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


@lru_cache(maxsize=4)
def get_canonical_model(schema_version: SchemaVersion) -> type[BaseModel]:
    """Return the canonical pydantic model type for a schema version."""

    if schema_version == "v1":
        from models.need_analysis import NeedAnalysisProfile

        return NeedAnalysisProfile
    if schema_version == "v2":
        from models.need_analysis_v2 import NeedAnalysisV2

        return NeedAnalysisV2
    raise ValueError(f"Unsupported schema version '{schema_version}'")


@lru_cache(maxsize=32)
def _load_need_analysis_legacy_cached(
    section_tuple: tuple[str, ...] | None,
    schema_version: str | None,
) -> dict[str, Any]:
    # ``schema_version`` is intentionally part of the cache key for legacy callers.
    try:
        return _build_need_analysis_v1_schema(sections=section_tuple)
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.warning("Falling back to disk schema after builder failure: %s", exc)
        schema = _load_json(_SCHEMA_PATH_V1)
        if section_tuple:
            return _trim_sections(schema, section_tuple)
        return schema


@lru_cache(maxsize=32)
def _get_need_analysis_schema_cached(
    schema_version: SchemaVersion,
    section_tuple: tuple[str, ...] | None,
) -> dict[str, Any]:
    try:
        if schema_version == "v1":
            return _build_need_analysis_v1_schema(sections=section_tuple)
        return _build_need_analysis_v2_schema(sections=section_tuple)
    except Exception as exc:  # pragma: no cover - defensive fallback
        if schema_version == "v1":
            logger.warning("Falling back to disk schema after builder failure: %s", exc)
            schema = _load_json(_SCHEMA_PATH_V1)
            if section_tuple:
                return _trim_sections(schema, section_tuple)
            return schema
        raise


def get_canonical_json_schema(
    *,
    schema_version: SchemaVersion,
    artifact: SchemaArtifact = "need_analysis",
    sections: Collection[str] | None = None,
) -> dict[str, Any]:
    """Return a canonical JSON schema for the requested version/artifact."""

    if artifact == "need_analysis":
        section_tuple = tuple(sections) if sections else None
        return deepcopy(_get_need_analysis_schema_cached(schema_version, section_tuple))
    if artifact == "vacancy_extraction":
        return _build_vacancy_extraction_schema(_version=schema_version)
    if artifact == "followups":
        return _build_followups_schema(_version=schema_version)
    raise ValueError(f"Unsupported schema artifact '{artifact}'")


_ALLOWED_ADAPTER_PATHS: tuple[AdapterPath, ...] = (("v1", "v2"),)


def get_allowed_adapter_paths() -> tuple[AdapterPath, ...]:
    """Return all permitted adapter paths in source->target order."""

    return _ALLOWED_ADAPTER_PATHS


def get_adapter(source_version: SchemaVersion, target_version: SchemaVersion) -> Callable[[Mapping[str, Any]], Any]:
    """Return adapter callable for a permitted migration path."""

    path = (source_version, target_version)
    if path == ("v1", "v2"):
        from adapters.v1_to_v2 import adapt_v1_to_v2

        return adapt_v1_to_v2
    raise ValueError(f"Unsupported adapter path: {source_version} -> {target_version}")


def adapt_payload(payload: Mapping[str, Any], *, source_version: SchemaVersion, target_version: SchemaVersion) -> Any:
    """Adapt ``payload`` across schema versions using allowed adapter paths only."""

    adapter = get_adapter(source_version, target_version)
    return adapter(payload)


def load_need_analysis_schema(
    *, sections: Collection[str] | None = None, schema_version: str | None = None
) -> dict[str, Any]:
    """Compatibility wrapper for legacy callers expecting v1 NeedAnalysis schema."""

    section_tuple = tuple(sections) if sections else None
    return deepcopy(_load_need_analysis_legacy_cached(section_tuple, schema_version))


def _flatten_schema_fields(schema: Mapping[str, Any], prefix: str = "") -> list[str]:
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
    schema = load_need_analysis_schema(sections=sections)
    return tuple(_flatten_schema_fields(schema))


def clear_schema_cache() -> None:
    _get_need_analysis_schema_cached.cache_clear()
    _load_need_analysis_legacy_cached.cache_clear()
    get_canonical_model.cache_clear()


__all__ = [
    "adapt_payload",
    "clear_schema_cache",
    "get_adapter",
    "get_allowed_adapter_paths",
    "get_canonical_json_schema",
    "get_canonical_model",
    "iter_need_analysis_field_paths",
    "load_need_analysis_schema",
]
