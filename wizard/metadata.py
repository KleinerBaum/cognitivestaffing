"""Shared wizard metadata consumed by the flow engine and router.

This module isolates the lightweight field/section relationships and the
critical-field helpers so that ``wizard.flow`` and ``wizard_router`` can import
what they need without triggering circular imports. Keeping the dependency graph
explicit also makes type-checking and unit tests straightforward.
"""

from __future__ import annotations

from typing import Callable, Final, Mapping, Sequence

import streamlit as st

from constants.keys import ProfilePaths, StateKeys
from question_logic import CRITICAL_FIELDS
from wizard._logic import get_in
from wizard_pages import WIZARD_PAGES
from wizard.company_validators import persist_contact_email, persist_primary_city

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
    "jobad": ("meta.",),
    "company": ("company.", "department."),
    "team": ("team.", "position.team_", "position.reporting_line", "location.", "employment."),
    "role_tasks": ("responsibilities.", "requirements.", "position.role_summary"),
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
    """Assemble required/extra field mappings used to track page completion."""

    mapping: dict[str, tuple[str, ...]] = {}
    for page in WIZARD_PAGES:
        extras = _PAGE_EXTRA_FIELDS.get(page.key, ())
        combined = tuple(dict.fromkeys((*page.required_fields, *extras)))
        if not combined:
            combined = (f"{VIRTUAL_PAGE_FIELD_PREFIX}{page.key}",)
        mapping[page.key] = combined
    return mapping


PAGE_PROGRESS_FIELDS: dict[str, tuple[str, ...]] = _build_page_progress_fields()

# Prefix-based overrides used to align families of fields with the correct wizard
# section without enumerating every schema path (e.g., all ``compensation.*``
# fields belong to the benefits step).
_SECTION_PREFIX_OVERRIDES: Final[dict[str, int]] = {
    "compensation.": PAGE_SECTION_INDEXES.get("benefits", COMPANY_STEP_INDEX),
}


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
PAGE_FIELD_MAP: dict[str, str] = {
    field: page_key
    for page_key, fields in PAGE_PROGRESS_FIELDS.items()
    for field in fields
}
CRITICAL_SECTION_ORDER: tuple[int, ...] = tuple(
    PAGE_SECTION_INDEXES[key] for key in _CRITICAL_SECTION_KEYS if key in PAGE_SECTION_INDEXES
)

# Fields collected early in the wizard but only blocking later sections when
# filtering via ``max_section``. The location city is displayed in the company
# step but shouldn't block the early company/role sections because salary and
# requirements insights can still run with just the country. Once the full
# wizard is considered we still treat it as critical.
SECTION_FILTER_OVERRIDES: dict[str, int] = {
    "position.seniority_level": PAGE_SECTION_INDEXES.get("team", COMPANY_STEP_INDEX),
    "employment.remote_percentage": PAGE_SECTION_INDEXES.get("team", COMPANY_STEP_INDEX),
    "process.interview_stages": PAGE_SECTION_INDEXES.get("interview", COMPANY_STEP_INDEX),
}

_VALIDATED_CRITICAL_FIELDS: Final[dict[str, Callable[[str | None], tuple[str | None, tuple[str, str] | None]]]] = {
    str(ProfilePaths.COMPANY_CONTACT_EMAIL): persist_contact_email,
    str(ProfilePaths.LOCATION_PRIMARY_CITY): persist_primary_city,
}


def resolve_section_for_field(field: str) -> int:
    """Return the wizard section index responsible for ``field``."""

    for prefix, section_index in _SECTION_PREFIX_OVERRIDES.items():
        if field.startswith(prefix):
            return section_index

    if field in SECTION_FILTER_OVERRIDES:
        return SECTION_FILTER_OVERRIDES[field]
    section = FIELD_SECTION_MAP.get(field)
    if section is not None:
        return section
    if CRITICAL_SECTION_ORDER:
        return CRITICAL_SECTION_ORDER[0]
    return COMPANY_STEP_INDEX


def field_belongs_to_page(field: str, page_key: str) -> bool:
    """Return ``True`` when ``field`` is part of the specified wizard page."""

    if PAGE_FIELD_MAP.get(field) == page_key:
        return True

    for prefix in PAGE_FOLLOWUP_PREFIXES.get(page_key, ()): 
        if field.startswith(prefix):
            return True

    return False


def _field_is_contextually_optional(field: str, profile_data: Mapping[str, object]) -> bool:
    """Return ``True`` when a field can be skipped given the current context."""

    work_policy = str(get_in(profile_data, "employment.work_policy", "") or "").strip().lower()
    travel_required = get_in(profile_data, "employment.travel_required", None)

    if field == str(ProfilePaths.LOCATION_PRIMARY_CITY) and work_policy == "remote":
        return True

    if field.startswith("employment.travel_") and travel_required is not True:
        return True

    return False


def _normalize_followup_priority(priority: str | None) -> str:
    """Normalize follow-up priority values to supported labels."""

    normalized = str(priority or "normal").strip().lower()
    if normalized not in {"critical", "normal", "optional"}:
        return "normal"
    return normalized


def _is_empty_value(value: object) -> bool:
    """Determine whether a profile value should be treated as missing."""

    if value is None:
        return True
    if isinstance(value, bool):
        return False
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, Mapping):
        return not any(value.values())
    if isinstance(value, (list, tuple, set)):
        return len(value) == 0
    return False


def _adjust_priority_for_context(
    field: str,
    priority: str,
    profile_data: Mapping[str, object],
) -> str | None:
    """Contextual priority adjustment for automatically generated follow-ups."""

    if _field_is_contextually_optional(field, profile_data):
        return None if field.startswith("employment.travel_") else "optional"

    seniority_raw = str(get_in(profile_data, "position.seniority_level", "") or "").strip().lower()
    is_junior = seniority_raw.startswith("junior") or "entry" in seniority_raw
    senior_lead_terms = {"lead", "manager", "head", "director", "vp", "chief", "principal"}
    is_senior_manager = any(term in seniority_raw for term in senior_lead_terms)

    if field in {"position.team_size", "position.supervises"}:
        if is_junior:
            return None
        if is_senior_manager:
            return "critical"

    return priority


def filter_followups_by_context(
    followups: Sequence[Mapping[str, object]],
    profile_data: Mapping[str, object],
) -> list[dict[str, object]]:
    """Filter and reprioritize follow-ups based on available context."""

    answered_fields = {
        str(item) for item in get_in(profile_data, "meta.followups_answered", []) if isinstance(item, str)
    }

    filtered: list[dict[str, object]] = []
    for item in followups:
        if not isinstance(item, Mapping):
            continue

        field = str(item.get("field", "") or "").strip()
        if not field or field in answered_fields:
            continue

        value = get_in(profile_data, field, None)
        if not _is_empty_value(value):
            continue

        base_priority = _normalize_followup_priority(str(item.get("priority", "")))
        adjusted_priority = _adjust_priority_for_context(field, base_priority, profile_data)
        if adjusted_priority is None:
            continue

        normalized: dict[str, object] = {
            "field": field,
            "question": item.get("question", ""),
            "priority": adjusted_priority,
        }

        for key in ("suggestions", "rationale", "depends_on", "prefill", "description", "ui_variant"):
            if key in item:
                normalized[key] = item[key]

        filtered.append(normalized)

    return filtered


def _lookup_string_value(field: str, profile_data: Mapping[str, object]) -> str | None:
    """Return the current string stored for ``field`` from widgets or profile."""

    raw_value = st.session_state.get(field)
    if isinstance(raw_value, str):
        return raw_value
    profile_value = get_in(profile_data, field, None)
    if isinstance(profile_value, str):
        return profile_value
    return None


def get_missing_critical_fields(*, max_section: int | None = None) -> list[str]:
    """Return critical fields missing from state or profile data."""

    missing: list[str] = []
    profile_data = st.session_state.get(StateKeys.PROFILE, {}) or {}
    for field in CRITICAL_FIELDS:
        if _field_is_contextually_optional(field, profile_data):
            continue
        field_section = resolve_section_for_field(field)
        if max_section is not None and field_section > max_section:
            continue
        validator = _VALIDATED_CRITICAL_FIELDS.get(field)
        if validator is not None:
            raw_value = _lookup_string_value(field, profile_data)
            validator(raw_value)
            profile_data = st.session_state.get(StateKeys.PROFILE, {}) or {}
            value = get_in(profile_data, field, None)
        else:
            value = st.session_state.get(field)
            if not value:
                value = get_in(profile_data, field, None)
        if isinstance(value, str):
            value = value.strip()
        if not value:
            missing.append(field)

    for question in st.session_state.get(StateKeys.FOLLOWUPS, []):
        if question.get("priority") == "critical":
            missing.append(question.get("field", ""))
    return missing


__all__ = [
    "COMPANY_STEP_INDEX",
    "CRITICAL_SECTION_ORDER",
    "filter_followups_by_context",
    "FIELD_SECTION_MAP",
    "PAGE_FIELD_MAP",
    "PAGE_FOLLOWUP_PREFIXES",
    "PAGE_PROGRESS_FIELDS",
    "PAGE_SECTION_INDEXES",
    "SECTION_FILTER_OVERRIDES",
    "VIRTUAL_PAGE_FIELD_PREFIX",
    "get_missing_critical_fields",
    "field_belongs_to_page",
    "resolve_section_for_field",
]
