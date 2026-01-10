from __future__ import annotations

from wizard.step_registry import WIZARD_STEPS, get_step, resolve_active_step_keys, step_keys


def test_step_registry_order() -> None:
    assert step_keys() == (
        "jobad",
        "company",
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
