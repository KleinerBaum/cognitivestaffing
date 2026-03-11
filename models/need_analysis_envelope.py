"""Envelope model for shadow-mode need-analysis reasoning artifacts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .evidence import EvidenceItem


class NeedAnalysisEnvelope(BaseModel):
    """Canonical envelope that wraps profile facts and derived reasoning."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    facts: dict[str, Any] = Field(default_factory=dict)
    inferences: list[dict[str, Any]] = Field(default_factory=list)
    gaps: list[dict[str, Any]] = Field(default_factory=list)
    plan: list[dict[str, Any]] = Field(default_factory=list)
    risks: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
