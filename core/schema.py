"""Utilities for the need analysis profile schema."""

from __future__ import annotations

from typing import Any, List, Mapping, Tuple, Union, get_args, get_origin

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
) -> Tuple[List[str], set[str]]:
    """Recursively collect field paths and list-typed fields."""

    paths: List[str] = []
    list_fields: set[str] = set()
    for name, field in model.model_fields.items():
        tp = _strip_optional(field.annotation)
        path = f"{prefix}{name}"
        origin = get_origin(tp)
        if isinstance(tp, type) and issubclass(tp, BaseModel):
            sub_paths, sub_lists = _collect_fields(tp, f"{path}.")
            paths.extend(sub_paths)
            list_fields.update(sub_lists)
        else:
            paths.append(path)
            if origin in (list, List):
                list_fields.add(path)
    return paths, list_fields


ALL_FIELDS, LIST_FIELDS = _collect_fields(NeedAnalysisProfile)

# Alias map for backward compatibility with legacy field names
# Using MappingProxyType to prevent accidental mutation.
ALIASES: Mapping[str, str] = MappingProxyType(
    {
        "date_of_employment_start": "meta.target_start_date",
        "requirements.hard_skills": "requirements.hard_skills_required",
        "requirements.soft_skills": "requirements.soft_skills_required",
    }
)


def coerce_and_fill(data: dict[str, Any]) -> NeedAnalysisProfile:
    """Validate ``data`` and ensure required fields are present."""

    return NeedAnalysisProfile.model_validate(data or {})


# Backwards compatibility alias
VacalyserJD = NeedAnalysisProfile
