"""Wizard helpers package."""

from __future__ import annotations

from typing import Any

from .runner import FIELD_SECTION_MAP, get_missing_critical_fields

from . import _agents as agents
from . import layout
from . import _logic as logic
from . import runner
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
    "FIELD_SECTION_MAP",
    "get_missing_critical_fields",
    "merge_unique_items",
    "normalize_text_area_list",
    "render_list_text_area",
    "render_onboarding_hero",
    "render_step_heading",
    "_render_autofill_suggestion",
    "SALARY_SLIDER_MAX",
    "SALARY_SLIDER_MIN",
    "SALARY_SLIDER_STEP",
    "unique_normalized",
    "_derive_salary_range_defaults",
    "_get_company_logo_bytes",
    "_set_company_logo",
    "_autofill_was_rejected",
    "_update_profile",
    "generate_interview_guide_content",
    "generate_job_ad_content",
]


RUNNER_EXPORTS: list[str] = []

for _name in sorted(dir(runner)):
    if _name.startswith("__") or _name in __all__:
        continue
    value: Any = getattr(runner, _name)
    globals()[_name] = value
    RUNNER_EXPORTS.append(_name)

__all__.extend(RUNNER_EXPORTS)
