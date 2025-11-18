"""Typed helpers for OpenAI API requests and retries."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence, TypedDict, TypeAlias

ToolCallable = Callable[..., Any]
UsageDict: TypeAlias = dict[str, int]


class ToolCallPayload(TypedDict, total=False):
    """Normalised representation of a tool invocation returned by the API."""

    id: str
    call_id: str
    type: str
    function: Mapping[str, Any] | None
    content: str | Sequence[Any] | None
    output: str | Sequence[Any] | None
    name: str | None


class ToolMessagePayload(TypedDict, total=False):
    """Tool execution payload that is appended to the message list."""

    role: str
    tool_call_id: str
    content: str


class FileSearchResult(TypedDict, total=False):
    """Subset of the metadata we persist from file-search results."""

    id: str
    chunk_id: str
    file_id: str
    text: str
    metadata: Mapping[str, Any] | None


FileSearchKey = tuple[str, str, str]


@dataclass(frozen=True)
class ResponsesRequest:
    """Payload prepared for a single OpenAI API invocation."""

    payload: dict[str, Any]
    model: str | None
    tool_specs: list[dict[str, Any]]
    tool_functions: Mapping[str, ToolCallable]
    candidate_models: list[str]
    api_mode_override: str | None = None


@dataclass
class RetryState:
    """Mutable containers that survive individual retry attempts."""

    accumulated_usage: UsageDict = field(default_factory=dict)
    last_tool_calls: list[ToolCallPayload] = field(default_factory=list)
    file_search_results: list[FileSearchResult] = field(default_factory=list)
    seen_file_search: set[FileSearchKey] = field(default_factory=set)


@dataclass
class ChatFallbackContext:
    """Book-keeping helper that tracks fallback models during retries."""

    candidates: list[str]
    attempted: set[str] = field(default_factory=set)

    def initial_model(self) -> str:
        if not self.candidates:
            raise RuntimeError("No model candidates resolved for request")
        return self.candidates[0]

    def register_failure(self, failed_model: str) -> str | None:
        self.attempted.add(failed_model)
        for candidate in self.candidates:
            if candidate not in self.attempted:
                return candidate
        return None


def build_fallback_context(model: str | None, candidates: Sequence[str]) -> ChatFallbackContext:
    """Return a fallback context with duplicate candidates removed."""

    unique: list[str] = []
    for candidate in [model, *candidates]:
        if not candidate:
            continue
        if candidate not in unique:
            unique.append(candidate)
    return ChatFallbackContext(unique)


def create_retry_state() -> RetryState:
    """Return a fresh :class:`RetryState` instance."""

    return RetryState()


__all__ = [
    "ToolCallPayload",
    "ToolMessagePayload",
    "UsageDict",
    "FileSearchResult",
    "FileSearchKey",
    "ResponsesRequest",
    "RetryState",
    "ChatFallbackContext",
    "build_fallback_context",
    "create_retry_state",
]
