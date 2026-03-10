"""Decision card entities for Need Analysis V2."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


DecisionState = Literal["proposed", "confirmed", "rejected"]


class DecisionCard(BaseModel):
    """Structured decision item used for review and export gating."""

    model_config = ConfigDict(extra="forbid")

    decision_id: str
    title: str
    field_path: str
    decision_state: DecisionState = "proposed"
    proposed_value: Any = None
    rationale: str = ""
