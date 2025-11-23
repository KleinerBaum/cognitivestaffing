"""Tests for contact normalization helpers."""

import pytest

from utils.normalization.contact_normalization import (
    normalize_phone_number,
    normalize_website_url,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        (" +49 (0)30-123 4567 ext. 89 ", "+49 30 1234567 ext 89"),
        ("030/1234567", "030 1234567"),
        ("tel.: 123", "123"),
        ("call me maybe", None),
        (None, None),
    ],
)
def test_normalize_phone_number_variants(raw: str | None, expected: str | None) -> None:
    assert normalize_phone_number(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        (" example.com/jobs ", "https://example.com/jobs"),
        ("HTTP://Sub.Example.com/jobs/", "http://sub.example.com/jobs"),
        ("", None),
        (None, None),
    ],
)
def test_normalize_website_url_variants(raw: str | None, expected: str | None) -> None:
    assert normalize_website_url(raw) == expected
