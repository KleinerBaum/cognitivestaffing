from __future__ import annotations

from core.schema import KEYS_CANONICAL
from wizard.metadata import PAGE_SECTION_INDEXES
from wizard.step_registry import WIZARD_STEPS, get_step, resolve_active_step_keys, step_keys


def test_step_registry_order() -> None:
    assert step_keys() == (
        "jobad",
        "company",
        "client",
        "team",
        "role_tasks",
        "skills",
        "benefits",
        "interview",
        "summary",
    )


def test_step_registry_keys_are_unique() -> None:
    keys = [step.key for step in WIZARD_STEPS]
    assert len(keys) == len(set(keys))


def test_step_registry_integrity() -> None:
    expected_step_order = (
        "jobad",
        "company",
        "client",
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
        "client": 1,
        "team": 2,
        "role_tasks": 3,
        "skills": 3,
        "benefits": 4,
        "interview": 5,
        "summary": 6,
    }

    assert step_keys() == expected_step_order
    assert PAGE_SECTION_INDEXES == expected_section_indexes

    required_fields = {field for step in WIZARD_STEPS for field in step.required_fields}
    unknown_fields = sorted(field for field in required_fields if field not in KEYS_CANONICAL)
    assert not unknown_fields, f"Unknown required_fields detected: {unknown_fields}"


def test_step_registry_lookup() -> None:
    step = get_step("team")
    assert step is not None
    assert step.key == "team"
    assert get_step("unknown") is None


def test_step_registry_active_keys_respects_schema() -> None:
    profile = {"position": {}}
    session_state = {"_schema": {"properties": {"company": {}, "position": {}}}}
    active = resolve_active_step_keys(profile, session_state)
    assert "team" not in active
