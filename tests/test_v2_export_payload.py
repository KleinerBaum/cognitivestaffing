from __future__ import annotations

from exports.transform import build_v2_export_payload


def test_build_v2_export_payload_excludes_proposed_decision() -> None:
    payload = {
        "role": {"title": "Existing"},
        "open_decisions": [
            {
                "decision_id": "d1",
                "title": "Role title",
                "field_path": "role.title",
                "decision_state": "proposed",
                "proposed_value": "Senior Engineer",
                "rationale": "pending",
                "blocking_exports": ["job_ad_markdown"],
            }
        ],
        "warnings": [],
    }

    export = build_v2_export_payload(payload, artifact_key="job_ad_markdown")

    assert export["role"]["title"] == "Existing"
    assert export["open_decisions"] == []
    assert any("d1" in warning for warning in export["warnings"])


def test_build_v2_export_payload_includes_confirmed_decision() -> None:
    payload = {
        "role": {"title": "Existing"},
        "open_decisions": [
            {
                "decision_id": "d2",
                "title": "Role title",
                "field_path": "role.title",
                "decision_state": "confirmed",
                "proposed_value": "Senior Engineer",
                "rationale": "approved",
                "blocking_exports": ["job_ad_markdown"],
            }
        ],
        "warnings": [],
    }

    export = build_v2_export_payload(payload, artifact_key="job_ad_markdown")

    assert export["role"]["title"] == "Senior Engineer"
    assert len(export["open_decisions"]) == 1
    assert export["open_decisions"][0]["decision_state"] == "confirmed"
    assert export["warnings"] == []
