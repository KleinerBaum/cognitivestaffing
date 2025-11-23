"""Shared type aliases for the wizard package."""

from __future__ import annotations

from typing import Sequence


LangPair = tuple[str, str]
LangSuggestionPair = tuple[Sequence[str], Sequence[str]]

# Bilingual text pair used throughout the wizard UI
LocalizedText = LangPair


__all__ = [
    "LangPair",
    "LangSuggestionPair",
    "LocalizedText",
]
