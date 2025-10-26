"""Tests for dynamic model routing fallbacks."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config


@pytest.fixture(autouse=True)
def reset_model_availability() -> None:
    """Ensure each test sees a clean availability cache."""

    config.clear_unavailable_models()
    yield
    config.clear_unavailable_models()


def test_extraction_uses_cost_optimised_chain() -> None:
    """Extraction should start on nano and cascade through mini → 4o → 4."""

    fallbacks = config.get_model_fallbacks_for(config.ModelTask.EXTRACTION)
    assert fallbacks[:5] == [
        config.GPT5_NANO,
        config.GPT5_MINI,
        config.GPT4O,
        config.GPT4,
        "gpt-3.5-turbo",
    ]


def test_fallback_to_mini_when_nano_unavailable(caplog: pytest.LogCaptureFixture) -> None:
    """When nano is unavailable we should warn and fall back to mini."""

    config.mark_model_unavailable(config.GPT5_NANO)
    with caplog.at_level(logging.WARNING, logger="cognitive_needs.model_routing"):
        model = config.get_first_available_model(config.ModelTask.EXTRACTION)
    assert model == config.GPT5_MINI
    assert "gpt-5.1-nano" in caplog.text
    assert config.GPT5_MINI in caplog.text


def test_fallback_cascades_to_gpt4o(caplog: pytest.LogCaptureFixture) -> None:
    """If both nano and mini are down, gpt-4o should be selected with telemetry."""

    config.mark_model_unavailable(config.GPT5_NANO)
    config.mark_model_unavailable(config.GPT5_MINI)
    with caplog.at_level(logging.WARNING, logger="cognitive_needs.model_routing"):
        model = config.get_first_available_model(config.ModelTask.EXTRACTION)
    assert model == config.GPT4O
    assert config.GPT5_NANO in caplog.text
    assert config.GPT5_MINI in caplog.text
    assert config.GPT4O in caplog.text


def test_default_model_prefers_cost_optimised_tier() -> None:
    """The module-level defaults should prefer GPT-5.1 mini when unset."""

    assert config.DEFAULT_MODEL == config.GPT5_MINI
    assert config.OPENAI_MODEL == config.GPT5_MINI
