"""Decision card entities for Need Analysis V2."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


DecisionState = Literal["proposed", "confirmed", "rejected"]
DecisionCategory = Literal["search", "selection", "candidate_communication", "other"]
ImpactArea = Literal["Search", "Selection", "Candidate-Communication"]


class DecisionCard(BaseModel):
    """Structured decision item used for review and export gating."""

    model_config = ConfigDict(extra="forbid")

    decision_id: str
    title: str
    field_path: str
    decision_state: DecisionState = "proposed"
    proposed_value: Any = None
    rationale: str = ""
    category: DecisionCategory = "other"
    impact_area: ImpactArea = "Selection"
    blocking_exports: list[str] = Field(default_factory=list)
    suggested_resolution_options: list[str] = Field(default_factory=list)
