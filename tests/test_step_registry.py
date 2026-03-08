from __future__ import annotations

from typing import Mapping

from core.schema import KEYS_CANONICAL
from wizard.metadata import PAGE_SECTION_INDEXES
from wizard.step_registry import WIZARD_STEPS, get_step, resolve_active_step_keys, step_keys


def test_step_registry_order() -> None:
    assert step_keys() == (
        "landing",
        "jobad",
        "company",
        "team",
        "role_tasks",
        "skills",
        "benefits",
        "interview",
        "summary",
    )


def test_step_registry_starts_with_landing() -> None:
    assert step_keys()[0] == "landing"


def test_step_registry_keys_are_unique() -> None:
    keys = [step.key for step in WIZARD_STEPS]
    assert len(keys) == len(set(keys))


def test_step_registry_integrity() -> None:
    expected_step_order = (
        "landing",
        "jobad",
        "company",
        "team",
        "role_tasks",
        "skills",
        "benefits",
        "interview",
        "summary",
    )
    expected_section_indexes = {
        "jobad": 0,
        "company": 1,
        "team": 2,
        "role_tasks": 3,
        "skills": 3,
        "benefits": 4,
        "interview": 5,
        "summary": 6,
    }

    assert step_keys() == expected_step_order
    assert "landing" not in PAGE_SECTION_INDEXES
    assert PAGE_SECTION_INDEXES == expected_section_indexes

    required_fields = {field for step in WIZARD_STEPS for field in step.required_fields}
    unknown_fields = sorted(field for field in required_fields if field not in KEYS_CANONICAL)
    assert not unknown_fields, f"Unknown required_fields detected: {unknown_fields}"


def test_landing_step_has_no_required_or_summary_fields() -> None:
    landing = get_step("landing")
    assert landing is not None
    assert landing.required_fields == ()
    assert landing.summary_fields == ()


def test_required_field_paths_remain_canonical() -> None:
    for step in WIZARD_STEPS:
        invalid_fields = [field for field in step.required_fields if field not in KEYS_CANONICAL]
        assert not invalid_fields, f"{step.key} has non-canonical required_fields: {invalid_fields}"


def test_step_registry_lookup() -> None:
    step = get_step("team")
    assert step is not None
    assert step.key == "team"
    assert get_step("unknown") is None


def test_step_registry_active_keys_respects_schema() -> None:
    profile: Mapping[str, object] = {"position": {}}
    session_state: Mapping[str, object] = {"_schema": {"properties": {"company": {}, "position": {}}}}
    active = resolve_active_step_keys(profile, session_state)
    assert "team" not in active
