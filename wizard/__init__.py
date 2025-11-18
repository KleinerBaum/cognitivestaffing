"""Wizard helpers package."""

from __future__ import annotations

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
from . import flow
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

for _name in sorted(dir(flow)):
    if _name.startswith("__") or _name in __all__:
        continue
    value: Any = getattr(flow, _name)
    globals()[_name] = value
    FLOW_EXPORTS.append(_name)

__all__.extend(FLOW_EXPORTS)
