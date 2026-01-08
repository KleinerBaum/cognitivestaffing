from __future__ import annotations

from wizard.step_registry import STEPS, get_step, step_keys


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
    keys = [step.key for step in STEPS]
    assert len(keys) == len(set(keys))


def test_step_registry_lookup() -> None:
    step = get_step("team")
    assert step is not None
    assert step.key == "team"
    assert get_step("unknown") is None
