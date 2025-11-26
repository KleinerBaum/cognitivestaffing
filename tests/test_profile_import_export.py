from __future__ import annotations

import json

from models.need_analysis import CURRENT_SCHEMA_VERSION
from state.autosave import build_snapshot, parse_snapshot, serialize_snapshot


def test_export_import_roundtrip_preserves_profile_and_state() -> None:
    profile = {
        "company": {"name": "Example Corp"},
        "position": {"job_title": "Data Scientist"},
    }
    wizard_state = {
        "current_step": "skills",
        "completed_steps": ["jobad", "company"],
        "skipped_steps": ["team"],
    }

    snapshot = build_snapshot(
        profile,
        wizard_state=wizard_state,
        lang="en",
        reasoning_mode="precise",
        step_index=3,
    )

    serialized = serialize_snapshot(snapshot)
    decoded = json.loads(serialized.decode("utf-8"))
    restored = parse_snapshot(decoded)

    assert restored["profile"]["schema_version"] == CURRENT_SCHEMA_VERSION
    assert restored["profile"]["company"]["name"] == "Example Corp"
    assert restored["wizard"]["current_step"] == "skills"
    assert restored["wizard"]["completed_steps"] == ["jobad", "company"]
    assert restored["meta"]["lang"] == "en"
    assert restored["meta"]["reasoning_mode"] == "precise"
    assert restored["meta"]["step_index"] == 3
