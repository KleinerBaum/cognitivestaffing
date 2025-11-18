"""Shared wizard metadata consumed by the flow engine and router.

This module isolates the lightweight field/section relationships and the
critical-field helpers so that ``wizard.flow`` and ``wizard_router`` can import
what they need without triggering circular imports. Keeping the dependency graph
explicit also makes type-checking and unit tests straightforward.
"""

from __future__ import annotations

from typing import Final

import streamlit as st

from constants.keys import StateKeys
from question_logic import CRITICAL_FIELDS
from wizard._logic import get_in
from pages import WIZARD_PAGES

# Index of the first data-entry step ("Unternehmen" / "Company").
COMPANY_STEP_INDEX: Final[int] = 1

PAGE_SECTION_INDEXES: Final[dict[str, int]] = {
    "jobad": 0,
    "company": COMPANY_STEP_INDEX,
    "team": COMPANY_STEP_INDEX + 1,
    "role_tasks": COMPANY_STEP_INDEX + 2,
    "skills": COMPANY_STEP_INDEX + 2,
    "benefits": COMPANY_STEP_INDEX + 3,
    "interview": COMPANY_STEP_INDEX + 4,
    "summary": COMPANY_STEP_INDEX + 5,
}

PAGE_FOLLOWUP_PREFIXES: Final[dict[str, tuple[str, ...]]] = {
    "company": ("company.",),
    "team": ("position.", "location.", "meta.", "employment."),
    "role_tasks": ("responsibilities.", "requirements."),
    "benefits": ("compensation.",),
    "interview": ("process.",),
    "summary": ("summary.",),
}

VIRTUAL_PAGE_FIELD_PREFIX: Final[str] = "__page__."

_CRITICAL_SECTION_KEYS: Final[tuple[str, ...]] = (
    "company",
    "team",
    "role_tasks",
    "benefits",
    "interview",
)

_PAGE_EXTRA_FIELDS: dict[str, tuple[str, ...]] = {
    "company": (
        "company.contact_name",
        "company.contact_email",
        "company.contact_phone",
        "location.primary_city",
        "location.country",
    ),
    "team": (
        "position.job_title",
        "position.role_summary",
        "meta.target_start_date",
    ),
    "role_tasks": ("responsibilities.items",),
    "skills": (
        "requirements.hard_skills_required",
        "requirements.soft_skills_required",
    ),
}


def _build_page_progress_fields() -> dict[str, tuple[str, ...]]:
    mapping: dict[str, tuple[str, ...]] = {}
    for page in WIZARD_PAGES:
        extras = _PAGE_EXTRA_FIELDS.get(page.key, ())
        combined = tuple(dict.fromkeys((*page.required_fields, *extras)))
        if not combined:
            combined = (f"{VIRTUAL_PAGE_FIELD_PREFIX}{page.key}",)
        mapping[page.key] = combined
    return mapping


PAGE_PROGRESS_FIELDS: dict[str, tuple[str, ...]] = _build_page_progress_fields()


def _build_field_section_map() -> dict[str, int]:
    """Derive mapping of schema fields to wizard section indexes."""

    mapping: dict[str, int] = {}
    for key, fields in PAGE_PROGRESS_FIELDS.items():
        section_index = PAGE_SECTION_INDEXES.get(key)
        if section_index is None:
            continue
        for field in fields:
            mapping[field] = section_index
    return mapping


FIELD_SECTION_MAP: dict[str, int] = _build_field_section_map()
CRITICAL_SECTION_ORDER: tuple[int, ...] = tuple(
    PAGE_SECTION_INDEXES[key] for key in _CRITICAL_SECTION_KEYS if key in PAGE_SECTION_INDEXES
)

# Fields collected early in the wizard but only blocking later sections when
# filtering via ``max_section``. The location city is displayed in the company
# step but shouldn't block the early company/role sections because salary and
# requirements insights can still run with just the country. Once the full
# wizard is considered we still treat it as critical.
SECTION_FILTER_OVERRIDES: dict[str, int] = {}


def resolve_section_for_field(field: str) -> int:
    """Return the wizard section index responsible for ``field``."""

    if field in SECTION_FILTER_OVERRIDES:
        return SECTION_FILTER_OVERRIDES[field]
    section = FIELD_SECTION_MAP.get(field)
    if section is not None:
        return section
    if CRITICAL_SECTION_ORDER:
        return CRITICAL_SECTION_ORDER[0]
    return COMPANY_STEP_INDEX


def get_missing_critical_fields(*, max_section: int | None = None) -> list[str]:
    """Return critical fields missing from state or profile data."""

    missing: list[str] = []
    profile_data = st.session_state.get(StateKeys.PROFILE, {})
    for field in CRITICAL_FIELDS:
        field_section = resolve_section_for_field(field)
        if max_section is not None and field_section > max_section:
            continue
        value = st.session_state.get(field)
        if not value:
            value = get_in(profile_data, field, None)
        if not value:
            missing.append(field)

    for question in st.session_state.get(StateKeys.FOLLOWUPS, []):
        if question.get("priority") == "critical":
            missing.append(question.get("field", ""))
    return missing


__all__ = [
    "COMPANY_STEP_INDEX",
    "CRITICAL_SECTION_ORDER",
    "FIELD_SECTION_MAP",
    "PAGE_FOLLOWUP_PREFIXES",
    "PAGE_PROGRESS_FIELDS",
    "PAGE_SECTION_INDEXES",
    "SECTION_FILTER_OVERRIDES",
    "VIRTUAL_PAGE_FIELD_PREFIX",
    "get_missing_critical_fields",
    "resolve_section_for_field",
]
