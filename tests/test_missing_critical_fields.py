"""Tests for post-processing of critical profile fields."""

from __future__ import annotations

from models.need_analysis import NeedAnalysisProfile
from state.ensure_state import _apply_critical_profile_defaults
from utils.normalization import NormalizedProfilePayload, normalize_profile


def test_critical_fields_receive_blank_defaults() -> None:
    """Critical profile fields should always exist even when empty."""

    profile: NormalizedProfilePayload = normalize_profile(NeedAnalysisProfile())
    profile["business_context"]["domain"] = None
    profile["company"]["contact_email"] = None
    profile["location"]["primary_city"] = None

    result = _apply_critical_profile_defaults(profile)

    assert result["business_context"]["domain"] == ""
    assert result["company"]["contact_email"] == ""
    assert result["location"]["primary_city"] == ""


def test_need_analysis_preserves_placeholders() -> None:
    """Validators keep blank placeholders for critical strings."""

    profile = NeedAnalysisProfile.model_validate(
        {
            "business_context": {"domain": ""},
            "company": {"contact_email": ""},
            "location": {
                "primary_city": "",
                "country": "   ",
                "onsite_ratio": "  ",
            },
        }
    )

    assert profile.business_context.domain == ""
    assert profile.company.contact_email == ""
    assert profile.location.primary_city == ""
    assert profile.location.country is None
    assert profile.location.onsite_ratio is None
