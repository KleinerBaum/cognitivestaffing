from __future__ import annotations

import json

from wizard_tools import safety


def test_redact_pii_replaces_email_characters() -> None:
    payload = json.loads(safety.redact_pii("talent@example.com"))

    assert payload["redacted"] == "talent[at]example.com"


def test_log_event_and_get_run_return_structured_payloads() -> None:
    event_payload = json.loads(
        safety.log_event(
            vacancy_id="vacancy-1",
            stage_id="stage-2",
            kind="info",
            payload={"message": "ok"},
        )
    )

    assert event_payload == {
        "logged": True,
        "vacancy_id": "vacancy-1",
        "stage_id": "stage-2",
        "kind": "info",
        "payload": {"message": "ok"},
    }

    run_payload = json.loads(safety.get_run("run-123"))
    assert run_payload == {"run": {"id": "run-123", "items": []}}
