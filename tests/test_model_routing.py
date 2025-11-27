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
import config.models as model_config


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def reset_model_availability() -> None:
    """Ensure each test sees a clean availability cache."""

    model_config.clear_unavailable_models()
    yield
    model_config.clear_unavailable_models()


def test_extraction_uses_cost_optimised_chain() -> None:
    """Extraction should start on GPT-4o mini and cascade through resilient fallbacks."""

    fallbacks = model_config.get_model_fallbacks_for(model_config.ModelTask.EXTRACTION)
    assert fallbacks[:4] == [
        model_config.GPT4O_MINI,
        model_config.GPT4O,
        model_config.GPT4,
        model_config.GPT35,
    ]


def test_fallback_to_gpt4o_when_mini_unavailable(caplog: pytest.LogCaptureFixture) -> None:
    """When GPT-4o mini is unavailable we should warn and fall back to GPT-4o."""

    model_config.mark_model_unavailable(model_config.GPT4O_MINI)
    with caplog.at_level(logging.WARNING, logger="cognitive_needs.model_routing"):
        model = model_config.get_first_available_model(model_config.ModelTask.EXTRACTION)
    assert model == model_config.GPT4O
    assert model_config.GPT4O_MINI in caplog.text
    assert model_config.GPT4O in caplog.text


def test_fallback_cascades_to_gpt4(caplog: pytest.LogCaptureFixture) -> None:
    """If newer tiers are down, GPT-4 should be selected with telemetry."""

    model_config.mark_model_unavailable(model_config.GPT4O_MINI)
    model_config.mark_model_unavailable(model_config.GPT4O)
    with caplog.at_level(logging.WARNING, logger="cognitive_needs.model_routing"):
        model = model_config.get_first_available_model(model_config.ModelTask.EXTRACTION)
    assert model == model_config.GPT4
    assert model_config.GPT4O_MINI in caplog.text
    assert model_config.GPT4O in caplog.text
    assert model_config.GPT4 in caplog.text


def test_default_model_prefers_cost_optimised_tier() -> None:
    """The module-level defaults should prefer the configured reasoning tier."""

    assert model_config.DEFAULT_MODEL == model_config.PRIMARY_MODEL_DEFAULT
    assert model_config.OPENAI_MODEL == model_config.PRIMARY_MODEL_DEFAULT


def test_reasoning_switch() -> None:
    """select_model should flip between nano tiers for reasoning workloads."""

    assert model_config.select_model("non_reasoning") == model_config.LIGHTWEIGHT_MODEL
    assert model_config.select_model("reasoning") == model_config.REASONING_MODEL
    assert model_config.select_model(model_config.ModelTask.EXTRACTION) == model_config.LIGHTWEIGHT_MODEL


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables should override the routing configuration."""

    monkeypatch.setenv("MODEL_ROUTING__REASONING", "gpt-5.1-mini-latest")
    try:
        reloaded = importlib.reload(config)
        assert reloaded.select_model("reasoning") == reloaded.GPT51_MINI
    finally:
        monkeypatch.delenv("MODEL_ROUTING__REASONING", raising=False)
        importlib.reload(config)
