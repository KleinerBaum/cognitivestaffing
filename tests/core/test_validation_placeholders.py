"""Tests for placeholder detection helpers."""

from __future__ import annotations

import pytest

from core.validation import is_placeholder


@pytest.mark.parametrize(
    "value",
    ["", "  ", "tbd", "TBD", "n/a", "NA", "keine", "-", "null", "Unknown", "k.A."],
)
def test_is_placeholder(value: str) -> None:
    """Values considered placeholders should return ``True``."""

    assert is_placeholder(value)


@pytest.mark.parametrize(
    "value",
    ["Berlin", "5000€", "Senior", "ja", 0, False],
)
def test_is_not_placeholder(value: object) -> None:
    """Non-placeholder values should not be flagged."""

    assert not is_placeholder(value)
