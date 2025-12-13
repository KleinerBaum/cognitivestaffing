from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

TContext = TypeVar("TContext")


class Agent(Generic[TContext]):
    """Lightweight stand-in for hosted agent definitions."""

    def __init__(self, name: str | None = None, **_: Any) -> None:
        self.name = name or "agent"


class Runner:
    """Minimal async runner shim used in tests."""

    async def run(
        self, agent: Agent[Any], input: list[Any], **_: Any
    ) -> Any:  # pragma: no cover - monkeypatched in tests
        raise NotImplementedError


@dataclass
class FileSearchTool:
    name: str | None = None
    max_num_results: int | None = None
    vector_store_ids: list[str] | None = None


@dataclass
class WebSearchTool(FileSearchTool):
    pass


def function_tool(
    func: Callable[..., Any] | None = None, **_: Any
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator stub that returns the wrapped function unchanged."""

    def decorator(inner: Callable[..., Any]) -> Callable[..., Any]:
        return inner

    if func is None:
        return decorator
    return decorator(func)


__all__ = ["Agent", "Runner", "FileSearchTool", "WebSearchTool", "function_tool"]
