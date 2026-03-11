from __future__ import annotations

from core.location_context import build_location_context, location_sensitive_followups
from wizard.services.gaps import field_is_contextually_optional


def test_build_location_context_normalizes_country_and_policies() -> None:
    context = build_location_context(
        {
            "location": {"primary_city": "in Berlin", "country": "Deutschland"},
            "employment": {"work_policy": "Remote", "visa_sponsorship": False, "relocation_support": True},
        }
    )

    assert context.city == "Berlin"
    assert context.country == "Germany"
    assert context.country_code == "DE"
    assert context.remote_policy == "remote"
    assert context.visa_policy == "not_available"
    assert context.relocation_policy == "offered"


def test_field_is_contextually_optional_uses_location_context() -> None:
    profile = {"employment": {"work_policy": "remote"}, "location": {"country": "Germany"}}

    assert field_is_contextually_optional("location.primary_city", profile) is True


def test_location_sensitive_followups_are_localized() -> None:
    profile = {"employment": {"work_policy": "hybrid"}, "location": {}}

    de_followups = location_sensitive_followups(profile, locale="de")
    en_followups = location_sensitive_followups(profile, locale="en")

    assert any("Land" in item["question"] for item in de_followups)
    assert any("country" in item["question"].lower() for item in en_followups)
