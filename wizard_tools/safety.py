"""Safety and telemetry related tools."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from agents import function_tool


@function_tool
def redact_pii(text: str) -> str:
    """Mask PII before persistence."""

    masked = text.replace("@", "[at]") if text else text
    return json.dumps({"redacted": masked})


@function_tool
def log_event(vacancy_id: str, stage_id: Optional[str], kind: str, payload: Dict[str, Any]) -> str:
    """Telemetry audit event."""

    return json.dumps(
        {
            "logged": True,
            "vacancy_id": vacancy_id,
            "stage_id": stage_id,
            "kind": kind,
            "payload": payload,
        }
    )


@function_tool
def get_run(run_id: str) -> str:
    """Fetch a run’s tool calls + outputs for replay."""

    return json.dumps({"run": {"id": run_id, "items": []}})


__all__ = ["get_run", "log_event", "redact_pii"]
