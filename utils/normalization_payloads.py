"""Typed payload shapes used by normalization utilities."""

from __future__ import annotations

from typing import TypedDict


class CompanyPayload(TypedDict, total=False):
    name: str | None
    brand_name: str | None
    industry: str | None
    hq_location: str | None
    size: str | None
    website: str | None
    mission: str | None
    culture: str | None
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    brand_keywords: str | None
    logo_url: str | None
    brand_color: str | None
    claim: str | None
    benefits: list[str]


class PositionPayload(TypedDict, total=False):
    job_title: str | None
    seniority_level: str | None
    team_structure: str | None
    reporting_line: str | None
    reports_to: str | None
    reporting_manager_name: str | None
    role_summary: str | None
    occupation_label: str | None
    occupation_uri: str | None
    occupation_group: str | None
    supervises: int | None
    performance_indicators: str | None
    decision_authority: str | None
    key_projects: str | None
    team_size: int | None
    customer_contact_required: bool | None
    customer_contact_details: str | None


class DepartmentPayload(TypedDict, total=False):
    name: str | None
    function: str | None
    leader_name: str | None
    leader_title: str | None
    strategic_goals: str | None


class TeamPayload(TypedDict, total=False):
    name: str | None
    mission: str | None
    reporting_line: str | None
    headcount_current: int | None
    headcount_target: int | None
    collaboration_tools: str | None
    locations: str | None


class LocationPayload(TypedDict, total=False):
    primary_city: str | None
    country: str | None
    onsite_ratio: str | None


class ResponsibilitiesPayload(TypedDict, total=False):
    items: list[str]


class SkillEntryPayload(TypedDict, total=False):
    name: str
    normalized_name: str | None
    esco_uri: str | None
    weight: float | None


class SkillMappingsPayload(TypedDict, total=False):
    hard_skills_required: list[SkillEntryPayload]
    hard_skills_optional: list[SkillEntryPayload]
    soft_skills_required: list[SkillEntryPayload]
    soft_skills_optional: list[SkillEntryPayload]
    tools_and_technologies: list[SkillEntryPayload]


class RequirementsPayload(TypedDict, total=False):
    hard_skills_required: list[str]
    hard_skills_optional: list[str]
    soft_skills_required: list[str]
    soft_skills_optional: list[str]
    tools_and_technologies: list[str]
    languages_required: list[str]
    languages_optional: list[str]
    certificates: list[str]
    certifications: list[str]
    language_level_english: str | None
    background_check_required: bool | None
    portfolio_required: bool | None
    reference_check_required: bool | None
    skill_mappings: SkillMappingsPayload


class EmploymentPayload(TypedDict, total=False):
    job_type: str | None
    work_policy: str | None
    contract_type: str | None
    work_schedule: str | None
    remote_percentage: int | None
    contract_end: str | None
    travel_required: bool | None
    travel_share: int | None
    travel_region_scope: str | None
    travel_regions: list[str]
    travel_continents: list[str]
    travel_details: str | None
    overtime_expected: bool | None
    relocation_support: bool | None
    relocation_details: str | None
    visa_sponsorship: bool | None
    security_clearance_required: bool | None
    shift_work: bool | None


class CompensationPayload(TypedDict, total=False):
    salary_provided: bool
    salary_min: float | None
    salary_max: float | None
    currency: str | None
    period: str | None
    variable_pay: bool | None
    bonus_percentage: float | None
    commission_structure: str | None
    equity_offered: bool | None
    benefits: list[str]


class StakeholderPayload(TypedDict, total=False):
    name: str
    role: str
    email: str | None
    primary: bool
    information_loop_phases: list[int]


class PhasePayload(TypedDict, total=False):
    name: str
    interview_format: str | None
    participants: list[str]
    docs_required: str | None
    assessment_tests: bool | None
    timeframe: str | None
    task_assignments: str | None


class ProcessPayload(TypedDict, total=False):
    interview_stages: int | None
    stakeholders: list[StakeholderPayload]
    phases: list[PhasePayload]
    recruitment_timeline: str | None
    hiring_process: list[str] | None
    process_notes: str | None
    application_instructions: str | None
    onboarding_process: str | None
    hiring_manager_name: str | None
    hiring_manager_role: str | None


class MetaPayload(TypedDict, total=False):
    target_start_date: str | None
    application_deadline: str | None
    followups_answered: list[str]


class NormalizedProfilePayload(TypedDict):
    company: CompanyPayload
    position: PositionPayload
    department: DepartmentPayload
    team: TeamPayload
    location: LocationPayload
    responsibilities: ResponsibilitiesPayload
    requirements: RequirementsPayload
    employment: EmploymentPayload
    compensation: CompensationPayload
    process: ProcessPayload
    meta: MetaPayload


__all__ = [
    "CompanyPayload",
    "PositionPayload",
    "DepartmentPayload",
    "TeamPayload",
    "LocationPayload",
    "ResponsibilitiesPayload",
    "SkillEntryPayload",
    "SkillMappingsPayload",
    "RequirementsPayload",
    "EmploymentPayload",
    "CompensationPayload",
    "StakeholderPayload",
    "PhasePayload",
    "ProcessPayload",
    "MetaPayload",
    "NormalizedProfilePayload",
]
