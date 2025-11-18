"""Regression tests for the onboarding lock guard."""

from __future__ import annotations

import pytest

import wizard.flow as wizard_flow


@pytest.mark.parametrize("available", [True, False])
def test_is_onboarding_locked_tracks_llm_state(monkeypatch: pytest.MonkeyPatch, available: bool) -> None:
    """Ensure the onboarding lock mirrors the LLM availability flag."""

    def _fake_is_llm_available() -> bool:
        return available

    monkeypatch.setattr(wizard_flow, "is_llm_available", _fake_is_llm_available)

    assert wizard_flow._is_onboarding_locked() is (not available)
