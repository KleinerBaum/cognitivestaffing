from __future__ import annotations

from wizard.step_registry import step_keys
from wizard.step_registry_runtime import (
    resolve_active_step_keys_for_version,
    resolve_nearest_active_step_key_for_version,
    resolve_wizard_version,
    step_keys_for_version,
)
from wizard.step_registry_v2 import step_keys_v2


def test_resolve_wizard_version_prefers_query_param_over_session_and_env(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_WIZARD_V2", "0")

    version = resolve_wizard_version(
        query_params={"wizard_version": "v2"},
        session_state={"wizard_version": "v1"},
    )

    assert version == "v2"


def test_step_keys_for_version_match_registries() -> None:
    assert step_keys_for_version("v1") == step_keys()
    assert step_keys_for_version("v2") == step_keys_v2()


def test_resolve_active_step_keys_for_version_stays_registry_consistent() -> None:
    profile = {"meta": {}}
    session_state = {"_schema": {"properties": {"company": {}, "team": {}, "position": {}}}}

    active_v1 = resolve_active_step_keys_for_version("v1", profile, session_state)
    active_v2 = resolve_active_step_keys_for_version("v2", profile, session_state)

    assert all(key in step_keys() for key in active_v1)
    assert active_v2 == step_keys_v2()


def test_resolve_nearest_active_step_key_for_version_returns_known_step_keys() -> None:
    active_v1 = ("landing", "jobad", "company", "skills", "summary")
    active_v2 = ("intake", "hiring_goal", "review")

    resolved_v1 = resolve_nearest_active_step_key_for_version("v1", "team", active_v1)
    resolved_v2 = resolve_nearest_active_step_key_for_version("v2", "real_work", active_v2)

    assert resolved_v1 in active_v1
    assert resolved_v2 in active_v2
