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
    """Extraction should start on GPT-4.1 nano and cascade through 4o → 4."""

    fallbacks = config.get_model_fallbacks_for(config.ModelTask.EXTRACTION)
    assert fallbacks[:4] == [
        config.GPT4O_MINI,
        config.GPT4O,
        config.GPT4,
        "gpt-3.5-turbo",
    ]


def test_fallback_to_gpt4o_when_mini_unavailable(caplog: pytest.LogCaptureFixture) -> None:
    """When GPT-4.1 nano is unavailable we should warn and fall back to GPT-4o."""

    config.mark_model_unavailable(config.GPT4O_MINI)
    with caplog.at_level(logging.WARNING, logger="cognitive_needs.model_routing"):
        model = config.get_first_available_model(config.ModelTask.EXTRACTION)
    assert model == config.GPT4O
    assert config.GPT4O_MINI in caplog.text
    assert config.GPT4O in caplog.text


def test_fallback_cascades_to_gpt4(caplog: pytest.LogCaptureFixture) -> None:
    """If GPT-4.1 nano and GPT-4o are down, GPT-4 should be selected with telemetry."""

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
