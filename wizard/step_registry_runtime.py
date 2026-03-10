"""Runtime selector for wizard step registries (V1/V2)."""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from typing import Final

from wizard.step_registry import (
    WIZARD_STEPS,
    StepDefinition,
    get_step,
    resolve_active_step_keys,
    resolve_nearest_active_step_key,
    step_keys,
)
from wizard.step_registry_v2 import WIZARD_STEPS_V2, get_step_v2, step_keys_v2

WizardVersion = str

_DEFAULT_VERSION: Final[WizardVersion] = "v1"


def resolve_wizard_version(
    *,
    query_params: Mapping[str, object] | None = None,
    session_state: Mapping[str, object] | None = None,
) -> WizardVersion:
    """Resolve wizard variant from explicit query parameter or feature flag."""

    query_params = query_params or {}
    for key in ("wizard", "wizard_version", "flow"):
        raw = query_params.get(key)
        candidate = _normalize_candidate(raw)
        if candidate in {"v1", "v2"}:
            return candidate

    if isinstance(session_state, Mapping):
        candidate = _normalize_candidate(session_state.get("wizard_version"))
        if candidate in {"v1", "v2"}:
            return candidate

    env_flag = os.getenv("ENABLE_WIZARD_V2", "0").strip().lower()
    if env_flag in {"1", "true", "yes", "on"}:
        return "v2"

    return _DEFAULT_VERSION


def get_wizard_steps(version: WizardVersion) -> tuple[StepDefinition, ...]:
    return WIZARD_STEPS_V2 if version == "v2" else WIZARD_STEPS


def get_step_for_version(version: WizardVersion, key: str) -> StepDefinition | None:
    return get_step_v2(key) if version == "v2" else get_step(key)


def step_keys_for_version(version: WizardVersion) -> tuple[str, ...]:
    return step_keys_v2() if version == "v2" else step_keys()


def resolve_active_step_keys_for_version(
    version: WizardVersion,
    profile: Mapping[str, object],
    session_state: Mapping[str, object],
) -> tuple[str, ...]:
    if version == "v2":
        return step_keys_v2()
    return resolve_active_step_keys(profile, session_state)


def resolve_nearest_active_step_key_for_version(
    version: WizardVersion,
    target_key: str,
    active_keys: Sequence[str],
) -> str | None:
    if not active_keys:
        return None
    if version == "v2":
        if target_key in active_keys:
            return target_key
        ordered = step_keys_v2()
        if target_key in ordered:
            start = ordered.index(target_key)
            for key in ordered[start + 1 :]:
                if key in active_keys:
                    return key
        return active_keys[0]
    return resolve_nearest_active_step_key(target_key, active_keys)


def _normalize_candidate(raw: object) -> str | None:
    if isinstance(raw, str):
        token = raw.strip().lower()
        if token in {"v1", "classic", "legacy"}:
            return "v1"
        if token in {"v2", "next", "new"}:
            return "v2"
        return token or None
    if isinstance(raw, Sequence) and not isinstance(raw, (bytes, bytearray, str)):
        for item in raw:
            normalized = _normalize_candidate(item)
            if normalized:
                return normalized
    return None
