"""Heuristic model routing helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
import unicodedata
from typing import Any, Iterable, Mapping, Sequence

from config.models import (
    GPT41_NANO,
    FAST,
    LIGHTWEIGHT_MODEL,
    ModelTask,
    QUALITY,
    REASONING_MODEL,
    is_model_available,
    normalise_model_name,
)

_WORD_PATTERN = re.compile(r"[\w\-]+", flags=re.UNICODE)
_LONG_CONTEXT_TOKEN_THRESHOLD = 300_000
_GPT5_TOOL_TYPES = frozenset({"file_search", "web_search", "web_search_preview", "code_interpreter"})
_COST_SAVER_CRITICAL_TASKS = frozenset(
    {
        ModelTask.JOB_AD.value,
        ModelTask.DOCUMENT_REFINEMENT.value,
        ModelTask.EXPLANATION.value,
    }
)


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
    tools: Sequence[Mapping[str, object]] | None = None,
    tool_choice: Any | None = None,
    cost_saver_enabled: bool = False,
    task: ModelTask | str | None = None,
) -> tuple[str, PromptCostEstimate]:
    """Return the preferred model for ``messages`` with the accompanying estimate."""

    estimate = estimate_prompt_complexity(messages)
    if estimate.total_tokens > _LONG_CONTEXT_TOKEN_THRESHOLD:
        candidate = GPT41_NANO
        if is_model_available(candidate):
            return candidate, estimate

    chosen = default_model
    normalised = (default_model or "").strip().lower()
    lightweight = LIGHTWEIGHT_MODEL.strip().lower()
    reasoning = REASONING_MODEL.strip().lower()
    nano = GPT41_NANO.strip().lower()

    if normalised == reasoning and estimate.complexity is PromptComplexity.SIMPLE:
        candidate = LIGHTWEIGHT_MODEL
        if is_model_available(candidate):
            chosen = candidate
    elif normalised == lightweight and estimate.complexity is PromptComplexity.COMPLEX:
        candidate = REASONING_MODEL
        if is_model_available(candidate):
            chosen = candidate
    elif normalised == lightweight and estimate.total_tokens < 120:
        candidate = GPT41_NANO
        if is_model_available(candidate):
            chosen = candidate
    elif normalised == nano and estimate.complexity is PromptComplexity.COMPLEX:
        candidate = REASONING_MODEL
        if is_model_available(candidate):
            chosen = candidate

    if _requires_gpt5_tools(tools, tool_choice) and not _is_gpt5_model(chosen):
        preferred = FAST if cost_saver_enabled else QUALITY
        if is_model_available(preferred):
            chosen = preferred

    task_key = _normalise_task_key(task)
    if cost_saver_enabled and task_key not in _COST_SAVER_CRITICAL_TASKS:
        chosen_normalised = normalise_model_name(chosen).lower()
        quality_normalised = normalise_model_name(QUALITY).lower()
        if chosen_normalised == quality_normalised and is_model_available(FAST):
            chosen = FAST

    return chosen, estimate


def _is_gpt5_model(model: str) -> bool:
    normalised = normalise_model_name(model).lower()
    return normalised.startswith("gpt-5")


def _normalise_task_key(task: ModelTask | str | None) -> str:
    if isinstance(task, ModelTask):
        return task.value
    if isinstance(task, str):
        return task.strip().lower()
    return ""


def _requires_gpt5_tools(
    tools: Sequence[Mapping[str, object]] | None,
    tool_choice: Any | None,
) -> bool:
    if _tool_choice_needs_gpt5(tool_choice):
        return True
    if not tools:
        return False
    for tool in tools:
        tool_type = _normalise_tool_type(tool)
        if tool_type in _GPT5_TOOL_TYPES:
            return True
    return False


def _tool_choice_needs_gpt5(tool_choice: Any | None) -> bool:
    if not tool_choice:
        return False
    if isinstance(tool_choice, str):
        return tool_choice.strip().lower() in _GPT5_TOOL_TYPES
    if isinstance(tool_choice, Mapping):
        tool_type = _normalise_tool_type(tool_choice)
        return tool_type in _GPT5_TOOL_TYPES
    return False


def _normalise_tool_type(tool: Mapping[str, object]) -> str:
    value = tool.get("type")
    if not isinstance(value, str):
        return ""
    return value.strip().lower()


__all__ = [
    "PromptComplexity",
    "PromptCostEstimate",
    "estimate_prompt_complexity",
    "route_model_for_messages",
]
