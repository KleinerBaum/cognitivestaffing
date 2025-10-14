"""LLM helper exports."""

from __future__ import annotations

from typing import Any

__all__ = ["run_dual_prompt"]


def __getattr__(name: str) -> Any:
    if name == "run_dual_prompt":
        from .dual import run_dual_prompt as _run_dual_prompt

        return _run_dual_prompt
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
