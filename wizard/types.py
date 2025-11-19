"""Shared type aliases for the wizard package."""

from __future__ import annotations

from typing import Sequence


LangPair = tuple[str, str]
LangSuggestionPair = tuple[Sequence[str], Sequence[str]]


__all__ = [
    "LangPair",
    "LangSuggestionPair",
]
