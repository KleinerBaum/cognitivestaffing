"""Shared wizard metadata consumed by runner and router.

This module isolates the lightweight field/section relationships and the
critical-field helpers so that ``wizard.runner`` and ``wizard_router`` can import
what they need without triggering circular imports. Keeping the dependency graph
explicit also makes type-checking and unit tests straightforward.
"""

from __future__ import annotations

from typing import Final

import streamlit as st

from constants.keys import StateKeys
from question_logic import CRITICAL_FIELDS
from wizard._logic import get_in

# Index of the first data-entry step ("Unternehmen" / "Company").
COMPANY_STEP_INDEX: Final[int] = 2

# Ordered field groups describing which canonical schema fields are edited in
# each wizard section. The numeric section index increments from
# ``COMPANY_STEP_INDEX`` onward so that other modules can reason about progress.
_SECTION_FIELD_GROUPS: tuple[tuple[str, ...], ...] = (
    (
        "company.name",
        "company.contact_name",
        "company.contact_email",
        "company.contact_phone",
        "company.brand_name",
        "company.industry",
        "company.hq_location",
        "company.size",
        "company.website",
        "company.mission",
        "company.culture",
        "company.brand_color",
        "company.logo_url",
        "location.primary_city",
        "location.country",
        "position.key_projects",
    ),
    (
        "position.job_title",
        "position.role_summary",
        "position.team_structure",
        "position.reporting_line",
        "position.reporting_manager_name",
        "position.customer_contact_required",
        "position.customer_contact_details",
        "department.name",
        "department.function",
        "department.leader_name",
        "department.leader_title",
        "department.strategic_goals",
        "team.name",
        "team.mission",
        "team.reporting_line",
        "team.headcount_current",
        "team.headcount_target",
        "team.collaboration_tools",
        "team.locations",
        "meta.target_start_date",
        "meta.application_deadline",
    ),
    (
        "responsibilities.items",
        "requirements.hard_skills_required",
        "requirements.soft_skills_required",
        "requirements.hard_skills_optional",
        "requirements.soft_skills_optional",
        "requirements.tools_and_technologies",
        "requirements.languages_required",
        "requirements.languages_optional",
        "requirements.certifications",
        "requirements.certificates",
        "requirements.background_check_required",
        "requirements.portfolio_required",
        "requirements.reference_check_required",
    ),
    (
        "employment.job_type",
        "employment.work_policy",
        "employment.contract_type",
        "employment.work_schedule",
        "employment.remote_percentage",
        "employment.travel_required",
        "employment.travel_share",
        "employment.travel_region_scope",
        "employment.travel_regions",
        "employment.travel_continents",
        "employment.travel_details",
        "employment.relocation_support",
        "employment.relocation_details",
        "employment.visa_sponsorship",
        "employment.overtime_expected",
        "employment.security_clearance_required",
        "employment.shift_work",
        "employment.contract_end",
        "compensation.salary_provided",
        "compensation.salary_min",
        "compensation.salary_max",
        "compensation.currency",
        "compensation.period",
        "compensation.variable_pay",
        "compensation.bonus_percentage",
        "compensation.commission_structure",
        "compensation.equity_offered",
        "compensation.benefits",
    ),
    (
        "process.interview_stages",
        "process.stakeholders",
        "process.phases",
        "process.recruitment_timeline",
        "process.process_notes",
        "process.application_instructions",
        "process.onboarding_process",
        "process.hiring_manager_name",
        "process.hiring_manager_role",
    ),
)


def _build_field_section_map() -> dict[str, int]:
    """Derive mapping of schema fields to wizard section indexes."""

    mapping: dict[str, int] = {}
    for offset, fields in enumerate(_SECTION_FIELD_GROUPS):
        section_index = COMPANY_STEP_INDEX + offset
        for field in fields:
            mapping[field] = section_index
    return mapping


FIELD_SECTION_MAP: dict[str, int] = _build_field_section_map()
CRITICAL_SECTION_ORDER: tuple[int, ...] = tuple(
    COMPANY_STEP_INDEX + index for index in range(len(_SECTION_FIELD_GROUPS))
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
    "SECTION_FILTER_OVERRIDES",
    "get_missing_critical_fields",
    "resolve_section_for_field",
]
