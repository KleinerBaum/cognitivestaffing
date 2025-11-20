"""Wizard helpers package."""

from __future__ import annotations

import importlib
from typing import Any

from .metadata import (
    COMPANY_STEP_INDEX,
    CRITICAL_SECTION_ORDER,
    FIELD_SECTION_MAP,
    SECTION_FILTER_OVERRIDES,
    get_missing_critical_fields,
    resolve_section_for_field,
)

from . import _agents as agents
from . import layout
from . import _logic as logic
from ._agents import (
    generate_interview_guide_content,
    generate_job_ad_content,
)
from .layout import (
    COMPACT_STEP_STYLE,
    inject_salary_slider_styles,
    _render_autofill_suggestion,
    render_list_text_area,
    render_onboarding_hero,
    render_step_heading,
    render_step_warning_banner,
)
from ._logic import (
    SALARY_SLIDER_MAX,
    SALARY_SLIDER_MIN,
    SALARY_SLIDER_STEP,
    _autofill_was_rejected,
    _derive_salary_range_defaults,
    _get_company_logo_bytes,
    _set_company_logo,
    _update_profile,
    merge_unique_items,
    normalize_text_area_list,
    unique_normalized,
)

__all__ = [
    "agents",
    "layout",
    "logic",
    "COMPACT_STEP_STYLE",
    "inject_salary_slider_styles",
    "COMPANY_STEP_INDEX",
    "CRITICAL_SECTION_ORDER",
    "FIELD_SECTION_MAP",
    "get_missing_critical_fields",
    "merge_unique_items",
    "normalize_text_area_list",
    "render_list_text_area",
    "render_onboarding_hero",
    "render_step_heading",
    "render_step_warning_banner",
    "SECTION_FILTER_OVERRIDES",
    "_render_autofill_suggestion",
    "SALARY_SLIDER_MAX",
    "SALARY_SLIDER_MIN",
    "SALARY_SLIDER_STEP",
    "resolve_section_for_field",
    "unique_normalized",
    "_derive_salary_range_defaults",
    "_get_company_logo_bytes",
    "_set_company_logo",
    "_autofill_was_rejected",
    "_update_profile",
    "generate_interview_guide_content",
    "generate_job_ad_content",
]


FLOW_EXPORTS: list[str] = []


def _load_flow_attribute(name: str) -> Any:
    """Lazily import ``wizard.flow`` to avoid circular imports."""

    flow = importlib.import_module(f"{__name__}.flow")

    value: Any = getattr(flow, name)
    if name not in globals():
        globals()[name] = value
    if name not in FLOW_EXPORTS:
        FLOW_EXPORTS.append(name)
    if name not in __all__:
        __all__.append(name)
    return value


def __getattr__(name: str) -> Any:
    """Load attributes from ``wizard.flow`` lazily while mirroring module semantics."""

    if name.startswith("__"):
        raise AttributeError(name)
    try:
        return _load_flow_attribute(name)
    except AttributeError as exc:  # pragma: no cover - mirrors module semantics
        raise AttributeError(f"module {__name__} has no attribute {name}") from exc


def __dir__() -> list[str]:  # pragma: no cover - convenience for REPLs
    """Expose dynamically populated exports for interactive environments."""

    return sorted(set(__all__ + FLOW_EXPORTS))
