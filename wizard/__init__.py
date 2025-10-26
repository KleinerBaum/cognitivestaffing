"""Wizard helpers package."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from . import _agents as agents
from . import _layout as layout
from . import _logic as logic
from ._agents import (
    generate_interview_guide_content,
    generate_job_ad_content,
)
from ._layout import (
    COMPACT_STEP_STYLE,
    inject_salary_slider_styles,
    render_onboarding_hero,
)
from ._logic import (
    SALARY_SLIDER_MAX,
    SALARY_SLIDER_MIN,
    SALARY_SLIDER_STEP,
    _derive_salary_range_defaults,
    _get_company_logo_bytes,
    _set_company_logo,
)

__all__ = [
    "agents",
    "layout",
    "logic",
    "COMPACT_STEP_STYLE",
    "inject_salary_slider_styles",
    "render_onboarding_hero",
    "SALARY_SLIDER_MAX",
    "SALARY_SLIDER_MIN",
    "SALARY_SLIDER_STEP",
    "_derive_salary_range_defaults",
    "_get_company_logo_bytes",
    "_set_company_logo",
    "generate_interview_guide_content",
    "generate_job_ad_content",
]


def _load_legacy_module() -> list[str]:
    """Load the historic ``wizard.py`` module and return the exported names."""

    module_path = Path(__file__).resolve().parent.parent / "wizard.py"
    source = module_path.read_text(encoding="utf-8")
    code = compile(source, str(module_path), "exec")
    exec_globals = globals()
    before = set(exec_globals.keys())
    exec(code, exec_globals, exec_globals)
    after = set(exec_globals.keys())

    legacy_exports: list[str] = []
    for name in sorted(after - before):
        if name.startswith("__"):
            continue
        legacy_exports.append(name)
    return legacy_exports


LEGACY_EXPORTS: list[str] = []

if not TYPE_CHECKING:
    LEGACY_EXPORTS = [name for name in _load_legacy_module() if name not in __all__]
    __all__.extend(LEGACY_EXPORTS)
