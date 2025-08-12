"""Tests for FIELD_SECTION_MAP coverage of critical fields."""

from wizard import FIELD_SECTION_MAP
from question_logic import CRITICAL_FIELDS


def test_all_critical_fields_mapped() -> None:
    """Ensure every critical field has a section mapping."""
    missing = CRITICAL_FIELDS - set(FIELD_SECTION_MAP)
    assert not missing, f"Missing mappings for: {sorted(missing)}"
