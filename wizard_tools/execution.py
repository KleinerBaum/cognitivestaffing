"""Execution control utilities for the wizard graph."""

from __future__ import annotations

import json
from typing import Any, Dict, Literal, Optional

from agents import function_tool


@function_tool
def run_stage(stage_id: str, inputs: Optional[Dict[str, Any]] = None) -> str:
    """Execute the stage’s domain op."""

    return json.dumps(
        {
            "stage_id": stage_id,
            "inputs": inputs or {},
            "outputs": {"ok": True},
            "reasoning_summary": "Executed.",
        }
    )


@function_tool
def run_all(vacancy_id: str) -> str:
    """Run all stages topologically."""

    return json.dumps({"vacancy_id": vacancy_id, "completed": True})


@function_tool
def retry_stage(stage_id: str, strategy: Literal["same_inputs", "regenerate", "raise_effort"] = "regenerate") -> str:
    """Retry a failed or low-confidence stage."""

    return json.dumps({"stage_id": stage_id, "retried": True, "strategy": strategy})


@function_tool
def set_model(stage_id: Optional[str], model: Literal["gpt-4o", "gpt-4o-mini", "gpt-5.1-nano", "gpt-5.1-mini"]) -> str:
    """Set model for a stage or globally."""

    return json.dumps({"ok": True, "stage_id": stage_id, "model": model})


@function_tool
def set_reasoning_effort(stage_id: Optional[str], level: Literal["minimal", "medium", "high"] = "minimal") -> str:
    """Set GPT-5 reasoning effort for a stage or globally."""

    return json.dumps({"ok": True, "stage_id": stage_id, "level": level})


@function_tool
def set_tool_choice(
    stage_id: Optional[str], mode: Literal["auto", "none", "force"] = "auto", function_name: Optional[str] = None
) -> str:
    """Control tool selection."""

    return json.dumps({"ok": True, "stage_id": stage_id, "mode": mode, "function_name": function_name})


@function_tool
def set_temperature(stage_id: Optional[str], value: float = 0.2) -> str:
    """Set sampling temperature (0..2)."""

    return json.dumps({"ok": True, "stage_id": stage_id, "temperature": value})


@function_tool
def set_max_output_tokens(stage_id: Optional[str], value: int = 2048) -> str:
    """Cap output tokens for a stage or globally."""

    return json.dumps({"ok": True, "stage_id": stage_id, "max_output_tokens": value})


__all__ = [
    "retry_stage",
    "run_all",
    "run_stage",
    "set_max_output_tokens",
    "set_model",
    "set_reasoning_effort",
    "set_temperature",
    "set_tool_choice",
]
