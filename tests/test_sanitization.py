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


def test_canonicalize_profile_payload_normalizes_empty_interview_stages() -> None:
    """Lists for interview stages are converted before validation."""

    payload = {"process": {"interview_stages": []}}
    canonical = canonicalize_profile_payload(payload)

    assert canonical["process"]["interview_stages"] is None

    profile = NeedAnalysisProfile.model_validate(canonical)
    assert profile.process.interview_stages is None


def test_canonicalize_profile_payload_converts_stage_list_to_int() -> None:
    """The first numeric value in the list becomes the stage count."""

    payload = {"process": {"interview_stages": ["3", "ignored"]}}
    canonical = canonicalize_profile_payload(payload)

    assert canonical["process"]["interview_stages"] == 3

    profile = NeedAnalysisProfile.model_validate(canonical)
    assert profile.process.interview_stages == 3
