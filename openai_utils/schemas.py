from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Mapping, Sequence

from config import STRICT_JSON


def build_json_schema_response_format(
    *, name: str, schema: Mapping[str, Any], strict: bool | None = None
) -> dict[str, Any]:
    """Return a Responses/Chat ``response_format`` payload for ``schema``.

    The OpenAI API expects JSON schema response formats to follow the nested
    ``{"type": "json_schema", "json_schema": {...}}`` structure. This helper
    centralises that construction to avoid invalid ``response_format.schema``
    parameters reaching the API.
    """

    sanitized_schema = sanitize_json_schema_for_responses(schema)
    json_schema_block: dict[str, Any] = {
        "name": name,
        "schema": deepcopy(sanitized_schema),
    }
    if strict is not None:
        json_schema_block["strict"] = strict

    return {
        "type": "json_schema",
        "json_schema": json_schema_block,
    }


def _assert_responses_schema_valid(schema: Mapping[str, Any], *, path: str = "$") -> None:
    if not isinstance(schema, Mapping):
        return

    if schema.get("type") == "object":
        properties = schema.get("properties")
        if isinstance(properties, Mapping):
            required = schema.get("required")
            if required is not None and set(required) != set(properties):
                missing = sorted(set(properties) - set(required or []))
                extra = sorted(set(required or []) - set(properties))
                raise ValueError(
                    "Responses JSON schema requires 'required' to include all properties at %s (missing=%s, extra=%s)"
                    % (path, ",".join(missing), ",".join(extra))
                )
            for key, value in properties.items():
                if isinstance(value, Mapping):
                    _assert_responses_schema_valid(value, path=f"{path}.{key}")

    items = schema.get("items")
    if isinstance(items, Mapping):
        _assert_responses_schema_valid(items, path=f"{path}[*]")

    for composite_key in ("anyOf", "oneOf", "allOf"):
        options = schema.get(composite_key)
        if isinstance(options, list):
            for index, option in enumerate(options):
                if isinstance(option, Mapping):
                    _assert_responses_schema_valid(option, path=f"{path}.{composite_key}[{index}]")


def sanitize_json_schema_for_responses(schema: Mapping[str, Any]) -> dict[str, Any]:
    from core.schema import ensure_responses_json_schema

    sanitized = ensure_responses_json_schema(schema)
    _assert_responses_schema_valid(sanitized)
    return sanitized


@dataclass(frozen=True)
class SchemaFormatBundle:
    name: str
    schema: dict[str, Any]
    strict: bool | None
    chat_response_format: dict[str, Any]
    responses_format: dict[str, Any]


def build_schema_format_bundle(json_schema_payload: Mapping[str, Any]) -> SchemaFormatBundle:
    if not isinstance(json_schema_payload, Mapping):
        raise TypeError("json_schema payload must be a mapping")

    schema_name_candidate = json_schema_payload.get("name")
    schema_name = str(schema_name_candidate or "").strip()
    if not schema_name:
        raise ValueError("json_schema payload requires a non-empty 'name'.")

    schema_body = json_schema_payload.get("schema")
    if not isinstance(schema_body, Mapping):
        raise ValueError("json_schema payload requires a mapping 'schema'.")

    strict_override = json_schema_payload.get("strict") if "strict" in json_schema_payload else None
    strict_value = STRICT_JSON if strict_override is None else bool(strict_override)

    sanitized_schema = deepcopy(sanitize_json_schema_for_responses(schema_body))

    chat_format = build_json_schema_response_format(
        name=schema_name, schema=sanitized_schema, strict=strict_value
    )

    responses_format = build_json_schema_response_format(
        name=schema_name, schema=sanitized_schema, strict=strict_value
    )

    return SchemaFormatBundle(
        name=schema_name,
        schema=sanitized_schema,
        strict=strict_value if strict_value else None,
        chat_response_format=chat_format,
        responses_format=responses_format,
    )


@lru_cache(maxsize=None)
def need_analysis_schema(
    sections: tuple[str, ...] | None = None, _schema_version: str | None = None
) -> dict[str, Any]:
    from core.schema import build_need_analysis_responses_schema

    return build_need_analysis_responses_schema(sections=sections)


def build_need_analysis_json_schema_payload(
    *, sections: Sequence[str] | None = None, schema_version: str | None = None
) -> dict[str, Any]:
    section_tuple = tuple(sections) if sections else None
    return {
        "name": "need_analysis_profile",
        "schema": deepcopy(need_analysis_schema(section_tuple, schema_version)),
    }


def sanitize_response_format_payload(response_format: Mapping[str, Any]) -> dict[str, Any]:
    cleaned = dict(response_format)
    format_type = str(cleaned.get("type") or "").lower()
    if format_type != "json_schema":
        return cleaned

    json_schema_block = cleaned.get("json_schema") if isinstance(cleaned.get("json_schema"), Mapping) else {}

    schema_payload = None
    name: str | None = None
    strict_value: bool | None = None

    if isinstance(json_schema_block, Mapping):
        schema_candidate = json_schema_block.get("schema")
        if isinstance(schema_candidate, Mapping):
            schema_payload = schema_candidate
        name_candidate = json_schema_block.get("name")
        if isinstance(name_candidate, str) and name_candidate.strip():
            name = name_candidate.strip()
        if "strict" in json_schema_block:
            strict_value = bool(json_schema_block.get("strict"))

    if schema_payload is None:
        schema_candidate = cleaned.get("schema") if isinstance(cleaned.get("schema"), Mapping) else None
        if isinstance(schema_candidate, Mapping):
            schema_payload = schema_candidate

    if name is None and isinstance(cleaned.get("name"), str):
        name_candidate = cleaned["name"].strip()
        if name_candidate:
            name = name_candidate

    if strict_value is None and "strict" in cleaned:
        strict_value = bool(cleaned.get("strict"))

    if schema_payload is None or name is None:
        return cleaned

    return build_json_schema_response_format(
        name=name,
        schema=schema_payload,
        strict=strict_value,
    )


__all__ = [
    "build_json_schema_response_format",
    "SchemaFormatBundle",
    "build_need_analysis_json_schema_payload",
    "build_schema_format_bundle",
    "need_analysis_schema",
    "sanitize_json_schema_for_responses",
    "sanitize_response_format_payload",
]
