"""Tests for field->step ownership resolution."""

from __future__ import annotations

from sidebar import _build_context
from wizard.metadata import PAGE_FIELD_MAP, resolve_step_key_for_field_path


def test_every_page_mapped_field_resolves_to_same_step() -> None:
    for field, page_key in PAGE_FIELD_MAP.items():
        assert resolve_step_key_for_field_path(field) == page_key


def test_prefix_based_fields_resolve_to_expected_steps() -> None:
    assert resolve_step_key_for_field_path("company.name") == "company"
    assert resolve_step_key_for_field_path("employment.work_policy") == "team"
    assert resolve_step_key_for_field_path("requirements.hard_skills_required") == "skills"
    assert resolve_step_key_for_field_path("compensation.salary_min") == "benefits"
    assert resolve_step_key_for_field_path("process.interview_stages") == "interview"


def test_unknown_field_falls_back_to_company_step() -> None:
    assert resolve_step_key_for_field_path("unknown.path") == "company"


def test_sidebar_context_groups_missing_fields_by_step_key(monkeypatch) -> None:
    monkeypatch.setattr("sidebar.get_missing_critical_fields", lambda: ["company.name", "process.interview_stages"])

    context = _build_context()

    assert set(context.missing_by_step) == {"company", "interview"}
