"""Heuristic model routing helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
import unicodedata
from typing import Iterable, Mapping, Sequence

from config import GPT5_MINI, GPT5_NANO, is_model_available

_WORD_PATTERN = re.compile(r"[\w\-]+", flags=re.UNICODE)


class PromptComplexity(StrEnum):
    """Discrete prompt complexity labels used by the router."""

    SIMPLE = "simple"
    COMPLEX = "complex"


@dataclass(frozen=True)
class PromptCostEstimate:
    """Summary statistics describing the analysed prompt."""

    total_tokens: int
    hard_word_count: int
    complexity: PromptComplexity


def _iter_message_text(messages: Sequence[Mapping[str, object]]) -> Iterable[str]:
    """Yield textual fragments from ``messages`` in a tolerant fashion."""

    for message in messages:
        if not isinstance(message, Mapping):
            continue
        content = message.get("content")
        if isinstance(content, str):
            if content:
                yield content
            continue
        if isinstance(content, Sequence):
            for chunk in content:
                if isinstance(chunk, Mapping):
                    text = chunk.get("text")
                    if isinstance(text, str) and text:
                        yield text
                elif isinstance(chunk, str) and chunk:
                    yield chunk


def _tokenise(text: str) -> Iterable[str]:
    for match in _WORD_PATTERN.finditer(text):
        yield match.group(0)


def _is_hard_word(word: str) -> bool:
    stripped = word.strip("_-")
    if len(stripped) >= 12:
        return True
    if any(ch.isdigit() for ch in stripped):
        return True
    accent_count = sum(1 for ch in stripped if ord(ch) > 127 and unicodedata.category(ch).startswith("L"))
    return accent_count >= 3


def estimate_prompt_complexity(messages: Sequence[Mapping[str, object]]) -> PromptCostEstimate:
    """Return an aggregate complexity estimate for ``messages``."""

    total_tokens = 0
    hard_words = 0
    for fragment in _iter_message_text(messages):
        tokens = list(_tokenise(fragment))
        total_tokens += len(tokens)
        hard_words += sum(1 for token in tokens if _is_hard_word(token))

    if total_tokens == 0:
        complexity = PromptComplexity.SIMPLE
    else:
        ratio = hard_words / float(total_tokens or 1)
        complexity = (
            PromptComplexity.COMPLEX
            if total_tokens >= 180 or hard_words >= 30 or ratio >= 0.25
            else PromptComplexity.SIMPLE
        )

    return PromptCostEstimate(total_tokens=total_tokens, hard_word_count=hard_words, complexity=complexity)


def route_model_for_messages(
    messages: Sequence[Mapping[str, object]],
    *,
    default_model: str,
) -> tuple[str, PromptCostEstimate]:
    """Return the preferred model for ``messages`` with the accompanying estimate."""

    estimate = estimate_prompt_complexity(messages)
    chosen = default_model
    normalised = (default_model or "").strip().lower()
    mini = GPT5_MINI.strip().lower()
    nano = GPT5_NANO.strip().lower()

    if normalised == mini and estimate.complexity is PromptComplexity.SIMPLE:
        candidate = GPT5_NANO
        if is_model_available(candidate):
            chosen = candidate
    elif normalised == nano and estimate.complexity is PromptComplexity.COMPLEX:
        candidate = GPT5_MINI
        if is_model_available(candidate):
            chosen = candidate

    return chosen, estimate


__all__ = [
    "PromptComplexity",
    "PromptCostEstimate",
    "estimate_prompt_complexity",
    "route_model_for_messages",
]
