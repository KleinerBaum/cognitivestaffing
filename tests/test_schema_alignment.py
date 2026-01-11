"""Schema alignment checks for prompts and generated artifacts."""

from __future__ import annotations

from typing import Any, Mapping, Set

from core.schema import ALL_FIELDS, build_need_analysis_responses_schema
from core.schema_registry import (
    iter_need_analysis_field_paths,
    load_need_analysis_schema,
)
from llm.prompts import FIELDS_ORDER


def _is_object_schema(schema: Mapping[str, Any]) -> bool:
    """Return ``True`` when a JSON schema node represents an object."""

    type_marker = schema.get("type")
    types: set[str] = set()
    if isinstance(type_marker, str):
        types.add(type_marker)
    elif isinstance(type_marker, list):
        types.update(str(entry) for entry in type_marker)
    return "object" in types or isinstance(schema.get("properties"), Mapping)


def _collect_schema_paths(schema: Mapping[str, Any], prefix: str = "") -> Set[str]:
    """Return dot-paths for every non-object property in ``schema``."""

    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        return set()

    fields: set[str] = set()
    for name, subschema in properties.items():
        path = f"{prefix}{name}"
        if _is_object_schema(subschema):
            nested = _collect_schema_paths(subschema, prefix=f"{path}.")
            if not nested and isinstance(subschema, Mapping) and subschema.get("additionalProperties") is not None:
                fields.add(path)
            else:
                fields.update(nested)
        else:
            fields.add(path)
    return fields


def test_prompt_schema_and_model_fields_align() -> None:
    """Ensure model, JSON schema, and prompt field lists cannot drift."""

    schema = load_need_analysis_schema()
    schema_fields = _collect_schema_paths(schema)
    registry_fields = set(iter_need_analysis_field_paths())
    model_fields = set(ALL_FIELDS)
    prompt_fields = set(FIELDS_ORDER)

    assert registry_fields == schema_fields, "Registry field paths must mirror JSON schema properties"
    assert list(iter_need_analysis_field_paths()) == FIELDS_ORDER, "Prompt ordering must follow registry order"
    assert FIELDS_ORDER == ALL_FIELDS, "Prompt field ordering must follow NeedAnalysisProfile"
    assert schema_fields == model_fields, (
        "JSON schema fields must match NeedAnalysisProfile dot-paths; run "
        "`python scripts/propagate_schema.py --apply` if they diverge."
    )
    assert prompt_fields == model_fields, (
        "Prompt field list must stay aligned with NeedAnalysisProfile; update llm/prompts.py if new fields are added."
    )


def test_schema_registry_tracks_builder_output() -> None:
    """The registry must return the canonical builder schema for all consumers."""

    registry_schema = load_need_analysis_schema()
    generated = build_need_analysis_responses_schema()

    assert registry_schema == generated


def test_schema_registry_can_trim_sections() -> None:
    """Registry section filtering should mirror the builder's behaviour."""

    sections = ["business_context", "position"]
    registry_schema = load_need_analysis_schema(sections=sections)
    generated = build_need_analysis_responses_schema(sections=sections)

    assert registry_schema == generated
