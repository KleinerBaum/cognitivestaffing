"""Registry for wizard steps and their canonical order."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class StepMeta:
    """Metadata for an individual wizard step. GREP:STEP_META_V1"""

    key: str


STEPS: Final[tuple[StepMeta, ...]] = (  # GREP:STEP_REGISTRY_V1
    StepMeta(key="jobad"),
    StepMeta(key="company"),
    StepMeta(key="team"),
    StepMeta(key="role_tasks"),
    StepMeta(key="skills"),
    StepMeta(key="benefits"),
    StepMeta(key="interview"),
    StepMeta(key="summary"),
)


def step_keys() -> tuple[str, ...]:
    """Return wizard step keys in canonical order."""

    return tuple(step.key for step in STEPS)


def get_step(key: str) -> StepMeta | None:
    """Lookup step metadata by key."""

    return next((step for step in STEPS if step.key == key), None)
