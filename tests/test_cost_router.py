"""Unit tests for the prompt cost router heuristics."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from llm.cost_router import (
    PromptComplexity,
    estimate_prompt_complexity,
    route_model_for_messages,
)


def _make_messages(text: str) -> list[dict[str, str]]:
    return [{"role": "user", "content": text}]


def test_short_prompt_routes_to_nano() -> None:
    messages = _make_messages("Summarise the meeting in two sentences.")
    model, estimate = route_model_for_messages(messages, default_model=config.GPT5_MINI)
    assert model == config.GPT5_NANO
    assert estimate.complexity is PromptComplexity.SIMPLE


def test_long_prompt_routes_to_mini() -> None:
    paragraph = " ".join(
        [
            "Please analyse the following competency matrix and identify",
            "significant discrepancies across seniority levels, focusing",
            "on nuanced skill gaps, certification requirements, and",
            "language expectations for global collaboration teams.",
        ]
        * 8
    )
    messages = _make_messages(paragraph)
    model, estimate = route_model_for_messages(messages, default_model=config.GPT5_NANO)
    assert model == config.GPT5_MINI
    assert estimate.complexity is PromptComplexity.COMPLEX


def test_multilingual_prompt_counts_long_compounds() -> None:
    text = (
        "Bitte erstelle einen Vergleich zwischen französischen und deutschen"
        " Einstellungsrichtlinien, inkludiere länderspezifische"
        " Kündigungsschutzbestimmungen und erläutere, wie dies die"
        " Collaboration-Strukturen beeinflusst."
    )
    messages = _make_messages(text)
    estimate = estimate_prompt_complexity(messages)
    assert estimate.total_tokens >= 15
    assert estimate.hard_word_count >= 5
    assert estimate.complexity is PromptComplexity.COMPLEX
