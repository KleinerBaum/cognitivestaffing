"""Envelope model for shadow-mode need-analysis reasoning artifacts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .evidence import EvidenceItem


class EnvelopeFacts(BaseModel):
    """Operational profile facts as a typed passthrough mapping."""

    model_config = ConfigDict(extra="allow")

    def as_dict(self) -> dict[str, Any]:
        """Return facts as a plain JSON-serialisable mapping."""

        return self.model_dump(mode="json")

    def __getitem__(self, key: str) -> Any:
        return self.as_dict()[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.as_dict().get(key, default)


class EnvelopeInference(BaseModel):
    """Derived reasoning statement kept in shadow mode."""

    model_config = ConfigDict(extra="allow")

    kind: str = "inference"
    field_path: str = ""
    statement: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class EnvelopeGap(BaseModel):
    """Missing information tracked for adaptive planning."""

    model_config = ConfigDict(extra="allow")

    field_path: str = ""
    question: str = ""
    priority: str = "normal"
    status: str = "open"


class EnvelopePlanItem(BaseModel):
    """Plan/action item for shadow-mode control-plane snapshots."""

    model_config = ConfigDict(extra="allow")

    action: str = "snapshot"
    status: str = "queued"
    mode: str = "shadow"
    trigger: str = ""
    step: str = ""


class EnvelopeRisk(BaseModel):
    """Potential ambiguity or extraction risk marker."""

    model_config = ConfigDict(extra="allow")

    code: str = ""
    level: str = "low"
    detail: str = ""
    status: str = "open"


class NeedAnalysisEnvelope(BaseModel):
    """Canonical envelope that wraps profile facts and derived reasoning."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    facts: dict[str, Any] = Field(default_factory=dict)
    inferences: list[EnvelopeInference] = Field(default_factory=list)
    gaps: list[EnvelopeGap] = Field(default_factory=list)
    plan: list[EnvelopePlanItem] = Field(default_factory=list)
    risks: list[EnvelopeRisk] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
