"""Tests for the canonical alias mapping and key registry."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from constants.keys import ProfilePaths
from core.schema import (
    ALIASES,
    ALL_FIELDS,
    KEYS_CANONICAL,
    WIZARD_ALIASES,
    WIZARD_KEYS_CANONICAL,
    canonicalize_profile_payload,
    canonicalize_wizard_payload,
)
from models.need_analysis import NeedAnalysisProfile
from pages import WIZARD_PAGES
from exports.models import RecruitingWizardExport


def _set_path(payload: dict[str, object], path: str, value: object) -> None:
    parts = path.split(".")
    cursor: dict[str, object] = payload
    for part in parts[:-1]:
        next_value = cursor.setdefault(part, {})
        if not isinstance(next_value, dict):
            raise AssertionError(f"Intermediate path '{part}' is not a dict for alias '{path}'")
        cursor = next_value  # type: ignore[assignment]
    cursor[parts[-1]] = value


def _get_path(payload: Mapping[str, object], path: str) -> object | None:
    cursor: object = payload
    for part in path.split("."):
        if not isinstance(cursor, Mapping):
            return None
        if part not in cursor:
            return None
        cursor = cursor[part]
    return cursor


def _flatten_paths(data: object, prefix: str = "") -> Iterable[str]:
    if isinstance(data, Mapping):
        for key, value in data.items():
            next_prefix = f"{prefix}.{key}" if prefix else key
            if isinstance(value, Mapping):
                yield from _flatten_paths(value, next_prefix)
            else:
                yield next_prefix
    else:
        if prefix:
            yield prefix


def test_alias_mapping_complete() -> None:
    """Ensure aliases map to canonical keys and are applied during canonicalisation."""

    assert set(KEYS_CANONICAL) == set(ALL_FIELDS)

    for alias, target in ALIASES.items():
        assert target in KEYS_CANONICAL, f"Alias target '{target}' is not canonical"

        sentinel = f"alias:{alias}"
        payload: dict[str, object] = {}
        _set_path(payload, alias, sentinel)
        canonical = canonicalize_profile_payload(payload)

        if target.startswith(f"{alias}."):
            alias_container = _get_path(canonical, alias)
            assert isinstance(alias_container, Mapping), f"Alias '{alias}' did not produce mapping for '{target}'"
        else:
            assert _get_path(canonical, alias) is None, f"Alias '{alias}' leaked into canonical payload"
        canonical_value = _get_path(canonical, target)
        assert canonical_value not in (None, {}), f"Alias '{alias}' not applied to canonical target '{target}'"
        if isinstance(canonical_value, list):
            assert canonical_value, f"Alias '{alias}' produced empty list for '{target}'"
        else:
            assert canonical_value == sentinel, f"Alias '{alias}' value changed unexpectedly for '{target}'"


def test_wizard_alias_mapping_complete() -> None:
    """Ensure wizard aliases map into canonical RecruitingWizard fields."""

    canonical_paths = set(WIZARD_KEYS_CANONICAL)
    for alias, target in WIZARD_ALIASES.items():
        assert target in canonical_paths, f"Wizard alias target '{target}' must be canonical"

        sentinel = f"wizard-alias:{alias}"
        payload: dict[str, object] = {}
        _set_path(payload, alias, sentinel)
        canonical = canonicalize_wizard_payload(payload)

        if target.startswith(f"{alias}."):
            alias_container = _get_path(canonical, alias)
            assert isinstance(
                alias_container, Mapping
            ), f"Wizard alias '{alias}' should keep nested mapping for '{target}'"
        else:
            assert (
                _get_path(canonical, alias) is None
            ), f"Wizard alias '{alias}' leaked into canonical payload"

        canonical_value = _get_path(canonical, target)
        assert canonical_value not in (None, {}), f"Wizard alias '{alias}' missing target '{target}'"
        if isinstance(canonical_value, list):
            assert canonical_value, f"Wizard alias '{alias}' produced empty list for '{target}'"
        else:
            assert canonical_value == sentinel, f"Wizard alias '{alias}' changed value unexpectedly"


def test_recruiting_wizard_export_handles_legacy_aliases() -> None:
    """Export helper should accept legacy wizard fields via alias mapping."""

    payload = {"position": {"department": "Business Operations"}}
    export = RecruitingWizardExport.from_payload(payload)

    assert (
        export.payload.department.name == "Business Operations"
    ), "Alias values must populate the canonical department.name"


OPTIONAL_WIZARD_FIELDS = {
    "company.benefits",
    "company.brand_name",
    "company.contact_email",
    "company.contact_name",
    "company.contact_phone",
    "company.culture",
    "company.hq_location",
    "company.industry",
    "company.size",
    "missing_fields.root",
    "position.customer_contact_details",
    "position.customer_contact_required",
    "position.reporting_manager_name",
    "position.job_title",
    "position.role_summary",
    "position.seniority_level",
    "sources.root",
    "requirements.background_check_required",
    "requirements.certificates",
    "requirements.reference_check_required",
    "requirements.portfolio_required",
    "employment.job_type",
    "employment.work_policy",
    "process.interview_stages",
    "role.title",
    "role.purpose",
    "role.outcomes",
    "role.employment_type",
    "role.work_model",
    "role.work_location",
    "role.seniority",
    "role.reports_to",
    "role.on_call",
    "tasks.core",
    "tasks.secondary",
    "tasks.success_metrics",
    "skills.must_have",
    "skills.nice_to_have",
    "skills.tools",
    "skills.languages",
    "skills.certifications",
    "benefits.salary_range",
    "benefits.currency",
    "benefits.bonus",
    "benefits.equity",
    "benefits.perks",
    "benefits.wellbeing",
    "benefits.relocation_support",
    "benefits.on_call",
    "interview_process.steps",
    "interview_process.interviewers",
    "interview_process.evaluation_criteria",
    "interview_process.decision_timeline",
    "interview_process.notes",
}


LEGACY_WIZARD_FIELDS = {
    "compensation.benefits",
    "compensation.bonus_percentage",
    "compensation.commission_structure",
    "compensation.equity_offered",
    "compensation.period",
    "compensation.salary_max",
    "compensation.salary_min",
    "employment.travel_required",
    "employment.visa_sponsorship",
    "process.application_instructions",
    "process.onboarding_process",
    "process.phases",
}


COMPLIANCE_FIELD_PATHS: tuple[str, ...] = (
    "requirements.background_check_required",
    "requirements.reference_check_required",
    "requirements.portfolio_required",
)


def test_profile_paths_cover_schema_and_ui() -> None:
    profile_dump = NeedAnalysisProfile().model_dump()
    dump_paths = set(_flatten_paths(profile_dump))
    canonical_paths = set(KEYS_CANONICAL)
    assert dump_paths == canonical_paths

    compliance_fields = set(COMPLIANCE_FIELD_PATHS)
    assert compliance_fields <= canonical_paths
    assert compliance_fields <= dump_paths
    alias_targets = {alias for alias, target in ALIASES.items() if target in compliance_fields}
    assert not alias_targets, f"Compliance fields should be canonical without aliases: {sorted(alias_targets)}"
    wizard_alias_targets = {alias for alias, target in WIZARD_ALIASES.items() if target in compliance_fields}
    assert not wizard_alias_targets, (
        f"Wizard aliases should not cover compliance fields: {sorted(wizard_alias_targets)}"
    )

    enum_paths = {member.value for member in ProfilePaths}
    assert enum_paths == canonical_paths

    wizard_paths: set[str] = set()
    for page in WIZARD_PAGES:
        wizard_paths.update(str(field) for field in page.required_fields)
        wizard_paths.update(str(field) for field in page.summary_fields)

    canonical_wizard_paths = set(WIZARD_KEYS_CANONICAL)
    missing_wizard = canonical_wizard_paths - wizard_paths - OPTIONAL_WIZARD_FIELDS
    assert not missing_wizard, f"Wizard pages missing coverage for: {sorted(missing_wizard)}"

    stray = wizard_paths - canonical_wizard_paths
    allowed_alias = {path for path in stray if path in WIZARD_ALIASES or path in LEGACY_WIZARD_FIELDS}
    unexpected_stray = stray - allowed_alias
    assert not unexpected_stray, f"Wizard pages reference unknown paths: {sorted(unexpected_stray)}"

    alias_coverage = {alias for alias, target in WIZARD_ALIASES.items() if target in wizard_paths}
    legacy_coverage = wizard_paths | alias_coverage
    legacy_alias_keys = set(WIZARD_ALIASES.keys())
    missing_legacy = (legacy_alias_keys - legacy_coverage) - OPTIONAL_WIZARD_FIELDS
    assert not missing_legacy, f"Legacy schema fields uncovered by wizard pages: {sorted(missing_legacy)}"
