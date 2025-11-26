"""Tests for dynamic model routing fallbacks."""

from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def reset_model_availability() -> None:
    """Ensure each test sees a clean availability cache."""

    config.clear_unavailable_models()
    yield
    config.clear_unavailable_models()


def test_extraction_uses_cost_optimised_chain() -> None:
    """Extraction should start on GPT-4o mini and cascade through resilient fallbacks."""

    fallbacks = config.get_model_fallbacks_for(config.ModelTask.EXTRACTION)
    assert fallbacks[:4] == [
        config.GPT4O_MINI,
        config.GPT4O,
        config.GPT4,
        config.GPT35,
    ]


def test_fallback_to_gpt4o_when_mini_unavailable(caplog: pytest.LogCaptureFixture) -> None:
    """When GPT-4o mini is unavailable we should warn and fall back to GPT-4o."""

    config.mark_model_unavailable(config.GPT4O_MINI)
    with caplog.at_level(logging.WARNING, logger="cognitive_needs.model_routing"):
        model = config.get_first_available_model(config.ModelTask.EXTRACTION)
    assert model == config.GPT4O
    assert config.GPT4O_MINI in caplog.text
    assert config.GPT4O in caplog.text


def test_fallback_cascades_to_gpt4(caplog: pytest.LogCaptureFixture) -> None:
    """If newer tiers are down, GPT-4 should be selected with telemetry."""

    config.mark_model_unavailable(config.GPT4O_MINI)
    config.mark_model_unavailable(config.GPT4O)
    with caplog.at_level(logging.WARNING, logger="cognitive_needs.model_routing"):
        model = config.get_first_available_model(config.ModelTask.EXTRACTION)
    assert model == config.GPT4
    assert config.GPT4O_MINI in caplog.text
    assert config.GPT4O in caplog.text
    assert config.GPT4 in caplog.text


def test_default_model_prefers_cost_optimised_tier() -> None:
    """The module-level defaults should prefer the configured reasoning tier."""

    assert config.DEFAULT_MODEL == config.REASONING_MODEL
    assert config.OPENAI_MODEL == config.REASONING_MODEL


def test_reasoning_switch() -> None:
    """select_model should flip between nano tiers for reasoning workloads."""

    assert config.select_model("non_reasoning") == config.LIGHTWEIGHT_MODEL
    assert config.select_model("reasoning") == config.REASONING_MODEL
    assert config.select_model(config.ModelTask.EXTRACTION) == config.LIGHTWEIGHT_MODEL


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables should override the routing configuration."""

    monkeypatch.setenv("MODEL_ROUTING__REASONING", "gpt-5.1-mini-latest")
    try:
        reloaded = importlib.reload(config)
        assert reloaded.select_model("reasoning") == reloaded.GPT51_MINI
    finally:
        monkeypatch.delenv("MODEL_ROUTING__REASONING", raising=False)
        importlib.reload(config)
