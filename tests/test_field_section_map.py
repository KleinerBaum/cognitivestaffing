"""Tests for FIELD_SECTION_MAP coverage of critical fields."""

from wizard import FIELD_SECTION_MAP
from question_logic import CRITICAL_FIELDS


def test_all_critical_fields_mapped() -> None:
    """Ensure every critical field has a section mapping."""
    assert "location.primary_city" in CRITICAL_FIELDS
    missing = CRITICAL_FIELDS - set(FIELD_SECTION_MAP)
    assert not missing, f"Missing mappings for: {sorted(missing)}"


def test_city_field_maps_to_company_section() -> None:
    """The city should be handled in the company section to gate section 1."""
    assert FIELD_SECTION_MAP.get("location.primary_city") == 1
