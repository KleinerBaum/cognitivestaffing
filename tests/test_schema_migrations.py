"""Tests for NeedAnalysisProfile schema migrations."""

import pytest

from core.schema import coerce_and_fill
from core.schema_migrations import migrate_profile
from models.need_analysis import CURRENT_SCHEMA_VERSION


def test_migrate_profile_adds_version_and_defaults() -> None:
    legacy_profile = {
        "company": {"name": "Acme"},
        "process": {"hiring_process": ["CV screen"]},
    }

    migrated = migrate_profile(legacy_profile)

    assert migrated["schema_version"] == CURRENT_SCHEMA_VERSION
    assert migrated["business_context"]["org_name"] == "Acme"
    assert migrated["company"]["name"] == "Acme"
    assert migrated["process"]["hiring_process"] == ["CV screen"]
    assert migrated["meta"]["followups_answered"] == []


def test_migrate_rejects_future_version() -> None:
    future_payload = {"schema_version": CURRENT_SCHEMA_VERSION + 1}

    with pytest.raises(ValueError):
        migrate_profile(future_payload)


def test_coerce_and_fill_sets_schema_version() -> None:
    payload = {"company": {"name": "Acme"}, "schema_version": 1}

    profile = coerce_and_fill(payload)

    assert profile.schema_version == CURRENT_SCHEMA_VERSION
