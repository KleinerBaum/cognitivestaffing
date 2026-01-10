"""Registry for wizard steps and their canonical order."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

StepPredicate = Callable[[Mapping[str, object], Mapping[str, object]], bool]


@dataclass(frozen=True)
class StepMeta:
    """Metadata for an individual wizard step. GREP:STEP_META_V1"""

    key: str
    is_active: StepPredicate | None = None


def _schema_has_section(session_state: Mapping[str, object], section: str) -> bool:
    schema = session_state.get("_schema")
    if not isinstance(schema, Mapping):
        return True
    properties = schema.get("properties")
    if not isinstance(properties, Mapping):
        return True
    return section in properties


def _team_step_active(profile: Mapping[str, object], session_state: Mapping[str, object]) -> bool:
    if not _schema_has_section(session_state, "team"):
        return False
    position = profile.get("position") if isinstance(profile, Mapping) else {}
    if isinstance(position, Mapping):
        supervises = position.get("supervises")
        if isinstance(supervises, (int, float)) and supervises <= 0:
            return False
    return True


STEPS: Final[tuple[StepMeta, ...]] = (  # GREP:STEP_REGISTRY_V1
    StepMeta(key="jobad"),
    StepMeta(key="company"),
    StepMeta(key="team", is_active=_team_step_active),
    StepMeta(key="role_tasks"),
    StepMeta(key="skills"),
    StepMeta(key="benefits"),
    StepMeta(key="interview"),
    StepMeta(key="summary"),
)


def step_keys() -> tuple[str, ...]:
    """Return wizard step keys in canonical order."""

    return tuple(step.key for step in STEPS)


def resolve_active_step_keys(profile: Mapping[str, object], session_state: Mapping[str, object]) -> tuple[str, ...]:
    """Return active wizard step keys in canonical order."""

    active: list[str] = []
    for step in STEPS:
        if step.is_active and not step.is_active(profile, session_state):
            continue
        active.append(step.key)
    return tuple(active)


def resolve_nearest_active_step_key(target_key: str, active_keys: Sequence[str]) -> str | None:
    """Return the nearest active step key for ``target_key``."""

    if target_key in active_keys:
        return target_key
    ordered_keys = step_keys()
    if target_key in ordered_keys:
        start_index = ordered_keys.index(target_key)
        for key in ordered_keys[start_index + 1 :]:
            if key in active_keys:
                return key
    return active_keys[0] if active_keys else None


def get_step(key: str) -> StepMeta | None:
    """Lookup step metadata by key."""

    return next((step for step in STEPS if step.key == key), None)
