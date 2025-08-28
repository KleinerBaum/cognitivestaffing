"""Utilities for the need analysis profile schema."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Tuple, Union, get_args, get_origin

from types import MappingProxyType

from pydantic import BaseModel

from models.need_analysis import NeedAnalysisProfile


def _strip_optional(tp: Any) -> Any:
    """Remove ``Optional`` wrapper from a type annotation."""

    origin = get_origin(tp)
    if origin is Union:
        args = [arg for arg in get_args(tp) if arg is not type(None)]
        if len(args) == 1:
            return args[0]
    return tp


def _collect_fields(
    model: type[BaseModel], prefix: str = ""
) -> Tuple[List[str], set[str], Dict[str, Any]]:
    """Recursively collect field paths, list-typed fields and types."""

    paths: List[str] = []
    list_fields: set[str] = set()
    types: Dict[str, Any] = {}
    for name, field in model.model_fields.items():
        tp = _strip_optional(field.annotation)
        path = f"{prefix}{name}"
        origin = get_origin(tp)
        if isinstance(tp, type) and issubclass(tp, BaseModel):
            sub_paths, sub_lists, sub_types = _collect_fields(tp, f"{path}.")
            paths.extend(sub_paths)
            list_fields.update(sub_lists)
            types.update(sub_types)
        else:
            paths.append(path)
            types[path] = tp
            if origin in (list, List):
                list_fields.add(path)
    return paths, list_fields, types


ALL_FIELDS, LIST_FIELDS, FIELD_TYPES = _collect_fields(NeedAnalysisProfile)
BOOL_FIELDS = {p for p, t in FIELD_TYPES.items() if t is bool}
INT_FIELDS = {p for p, t in FIELD_TYPES.items() if t is int}
FLOAT_FIELDS = {p for p, t in FIELD_TYPES.items() if t is float}

# Alias map for backward compatibility with legacy field names
# Using MappingProxyType to prevent accidental mutation.
ALIASES: Mapping[str, str] = MappingProxyType(
    {
        "date_of_employment_start": "meta.target_start_date",
        "requirements.hard_skills": "requirements.hard_skills_required",
        "requirements.soft_skills": "requirements.soft_skills_required",
        "city": "location.primary_city",
        "brand name": "company.brand_name",
        "application deadline": "meta.application_deadline",
    }
)


def coerce_and_fill(data: Mapping[str, Any] | None) -> NeedAnalysisProfile:
    """Validate ``data`` and ensure required fields are present.

    The function also maps legacy alias keys defined in ``ALIASES`` to the
    current schema paths before validation. Nested paths use dot-notation and
    are created on demand.
    """

    def _pop_path(obj: dict[str, Any], path: str, default: Any) -> Any:
        parts = path.split(".")
        cursor: Any = obj
        for part in parts[:-1]:
            if not isinstance(cursor, dict) or part not in cursor:
                return default
            cursor = cursor[part]
        return cursor.pop(parts[-1], default)

    def _set_path(obj: dict[str, Any], path: str, value: Any) -> None:
        parts = path.split(".")
        cursor: Any = obj
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
        cursor[parts[-1]] = value

    data = {**(data or {})}
    sentinel = object()
    for alias, target in ALIASES.items():
        val = _pop_path(data, alias, sentinel)
        if val is not sentinel:
            _set_path(data, target, val)
    return NeedAnalysisProfile.model_validate(data)


# Backwards compatibility aliases
VacalyserProfile = NeedAnalysisProfile
VacalyserJD = NeedAnalysisProfile  # pragma: no cover - legacy alias
