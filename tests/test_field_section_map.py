"""Tests for FIELD_SECTION_MAP coverage of critical fields."""

from wizard import FIELD_SECTION_MAP
from question_logic import CRITICAL_FIELDS


def test_all_critical_fields_mapped() -> None:
    """Ensure every critical field has a section mapping."""
    assert "location.primary_city" in CRITICAL_FIELDS
    missing = CRITICAL_FIELDS - set(FIELD_SECTION_MAP)
    assert not missing, f"Missing mappings for: {sorted(missing)}"


def test_city_field_maps_to_company_section() -> None:
    """The city should be handled in the company section to gate the first data entry step."""
    assert FIELD_SECTION_MAP.get("location.primary_city") == 1
    assert FIELD_SECTION_MAP.get("company.contact_email") == 1
    assert FIELD_SECTION_MAP.get("company.contact_name") == 1
    assert FIELD_SECTION_MAP.get("business_context.domain") == 1


def test_team_context_fields_map_to_second_section() -> None:
    """Department and team fields must be captured in the second data entry section."""
    assert FIELD_SECTION_MAP.get("department.name") == 2
    assert FIELD_SECTION_MAP.get("team.reporting_line") == 2
    assert FIELD_SECTION_MAP.get("position.reporting_manager_name") == 2
    assert FIELD_SECTION_MAP.get("meta.target_start_date") == 2
