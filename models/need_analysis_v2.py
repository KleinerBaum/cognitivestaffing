"""Pydantic data model for the Need Analysis V2 contract."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from models.decision_card import DecisionCard
from models.evidence import EvidenceItem


class IntakeBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_language: str = ""
    raw_input: str = ""
    target_locale: str = ""


class RoleBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = ""
    summary: str = ""
    seniority: str = ""
    department: str = ""
    team: str = ""
    reports_to: str = ""


class WorkBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    responsibilities: list[str] = Field(default_factory=list)
    location: str = ""
    work_policy: str = ""
    travel_required: bool | None = None


class RequirementsBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hard_skills_required: list[str] = Field(default_factory=list)
    hard_skills_optional: list[str] = Field(default_factory=list)
    soft_skills_required: list[str] = Field(default_factory=list)
    soft_skills_optional: list[str] = Field(default_factory=list)
    languages_required: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


class ConstraintsBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visa_sponsorship: bool | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    currency: str = ""
    timeline: str = ""


class SelectionBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    process_steps: list[str] = Field(default_factory=list)
    stakeholders: list[str] = Field(default_factory=list)


class NeedAnalysisV2(BaseModel):
    """Canonical V2 profile with explicit decision-gating for exports."""

    model_config = ConfigDict(extra="forbid")

    intake: IntakeBlock = Field(default_factory=IntakeBlock)
    role: RoleBlock = Field(default_factory=RoleBlock)
    work: WorkBlock = Field(default_factory=WorkBlock)
    requirements: RequirementsBlock = Field(default_factory=RequirementsBlock)
    constraints: ConstraintsBlock = Field(default_factory=ConstraintsBlock)
    selection: SelectionBlock = Field(default_factory=SelectionBlock)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    open_decisions: list[DecisionCard] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    def confirmed_decisions(self) -> list[DecisionCard]:
        """Return only decisions that may flow into export inputs."""

        return [card for card in self.open_decisions if card.decision_state == "confirmed"]

    def export_input(self) -> dict[str, Any]:
        """Build export input; only confirmed decisions are applied."""

        payload = self.model_dump(mode="json")
        payload["open_decisions"] = [
            card.model_dump(mode="json") for card in self.open_decisions if card.decision_state == "confirmed"
        ]
        return payload
