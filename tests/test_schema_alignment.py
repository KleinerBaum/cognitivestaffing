"""Schema alignment checks for prompts and generated artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Set

from core.schema import ALL_FIELDS
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
            fields.update(_collect_schema_paths(subschema, prefix=f"{path}."))
        else:
            fields.add(path)
    return fields


def test_prompt_schema_and_model_fields_align() -> None:
    """Ensure model, JSON schema, and prompt field lists cannot drift."""

    schema = json.loads(Path("schema/need_analysis.schema.json").read_text())
    schema_fields = _collect_schema_paths(schema)
    model_fields = set(ALL_FIELDS)
    prompt_fields = set(FIELDS_ORDER)

    assert FIELDS_ORDER == ALL_FIELDS, "Prompt field ordering must follow NeedAnalysisProfile"
    assert schema_fields == model_fields, (
        "JSON schema fields must match NeedAnalysisProfile dot-paths; run "
        "`python scripts/propagate_schema.py --apply` if they diverge."
    )
    assert prompt_fields == model_fields, (
        "Prompt field list must stay aligned with NeedAnalysisProfile; update llm/prompts.py if new fields are added."
    )
