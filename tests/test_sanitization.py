"""Regression tests for URL sanitization guards."""

from __future__ import annotations

from core.schema import canonicalize_profile_payload, canonicalize_wizard_payload
from models.need_analysis import NeedAnalysisProfile


def test_empty_url_becomes_none() -> None:
    """Blank logo URLs are normalised to ``None`` before validation."""

    payload = {"company": {"logo_url": "   "}}
    canonical = canonicalize_profile_payload(payload)

    assert canonical["company"]["logo_url"] is None

    profile = NeedAnalysisProfile.model_validate(canonical)
    assert profile.company.logo_url is None


def test_wizard_empty_url_becomes_none() -> None:
    """Wizard payloads also sanitise cleared logo URLs."""

    payload = {"company": {"logo_url": ""}}
    canonical = canonicalize_wizard_payload(payload)

    assert canonical["company"]["logo_url"] is None
