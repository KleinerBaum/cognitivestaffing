"""Canonical confidence metadata models and adapters."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Final, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConfidenceTier(StrEnum):
    """Classification of how confident the system is in a field value."""

    RULE_STRONG = "rule_strong"
    AI_ASSISTED = "ai_assisted"


DEFAULT_AI_TIER: Final[ConfidenceTier] = ConfidenceTier.AI_ASSISTED
RULE_LOCK_TIER: Final[ConfidenceTier] = ConfidenceTier.RULE_STRONG


class ConfidenceMeta(BaseModel):
    """Confidence metadata for a single profile field."""

    model_config = ConfigDict(extra="forbid")

    source: str = "llm"
    tier: str = DEFAULT_AI_TIER.value
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    note: str | None = None


class EvidenceMeta(BaseModel):
    """Evidence metadata for a field value."""

    model_config = ConfigDict(extra="allow")

    source_text: str | None = None
    block_type: str | None = None
    block_index: int | None = None
    document_source: str | None = None
    page: int | None = None
    inferred: bool = False
    source_kind: str | None = None


class RecoveryMeta(BaseModel):
    """Metadata for extraction recovery/fallback events."""

    model_config = ConfigDict(extra="forbid")

    invalid_json: bool = False
    repaired: bool = False
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    errors: list[str] = Field(default_factory=list)
    low_confidence_fields: list[str] = Field(default_factory=list)


class LockingMeta(BaseModel):
    """Metadata for locking/high-confidence field ownership."""

    model_config = ConfigDict(extra="forbid")

    locked_fields: list[str] = Field(default_factory=list)
    high_confidence_fields: list[str] = Field(default_factory=list)


class CanonicalProfileMetadata(BaseModel):
    """Canonical profile metadata envelope used by access helpers."""

    model_config = ConfigDict(extra="allow")

    version: Literal[1] = 1
    confidence: dict[str, ConfidenceMeta] = Field(default_factory=dict)
    evidence: dict[str, EvidenceMeta] = Field(default_factory=dict)
    recovery: RecoveryMeta = Field(default_factory=RecoveryMeta)
    locking: LockingMeta = Field(default_factory=LockingMeta)

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, Mapping) else {}

    @field_validator("evidence", mode="before")
    @classmethod
    def _coerce_evidence(cls, value: Any) -> dict[str, Any]:
        return dict(value) if isinstance(value, Mapping) else {}


def _coerce_score(raw: Any) -> float | None:
    if isinstance(raw, (int, float)):
        value = float(raw)
        return max(0.0, min(1.0, value))
    return None


def adapt_legacy_metadata(raw: Mapping[str, Any] | None) -> CanonicalProfileMetadata:
    """Adapt legacy ``profile_metadata`` mappings into canonical metadata."""

    if not isinstance(raw, Mapping):
        return CanonicalProfileMetadata()

    if raw.get("version") == 1 and isinstance(raw.get("confidence"), Mapping):
        return CanonicalProfileMetadata.model_validate(raw)

    confidence_payload: dict[str, dict[str, Any]] = {}
    legacy_confidence = raw.get("field_confidence")
    if isinstance(legacy_confidence, Mapping):
        for path, payload in legacy_confidence.items():
            if not isinstance(path, str):
                continue
            entry = dict(payload) if isinstance(payload, Mapping) else {"score": _coerce_score(payload)}
            if entry.get("score") is None and entry.get("confidence") is None:
                entry["score"] = _coerce_score(payload)
            confidence_payload[path] = entry

    evidence_payload: dict[str, dict[str, Any]] = {}
    rules_payload = raw.get("rules")
    if isinstance(rules_payload, Mapping):
        for path, payload in rules_payload.items():
            if isinstance(path, str) and isinstance(payload, Mapping):
                evidence_payload[path] = dict(payload)

    recovery_payload = raw.get("llm_recovery") if isinstance(raw.get("llm_recovery"), Mapping) else {}
    locking_payload = {
        "locked_fields": list(raw.get("locked_fields") or []),
        "high_confidence_fields": list(raw.get("high_confidence_fields") or []),
    }

    return CanonicalProfileMetadata(
        confidence=confidence_payload,
        evidence=evidence_payload,
        recovery=dict(recovery_payload),
        locking=locking_payload,
    )


def export_metadata(metadata: CanonicalProfileMetadata) -> dict[str, Any]:
    """Export canonical metadata including legacy-compatible projection."""

    payload = metadata.model_dump(mode="python", exclude_none=True)
    payload["field_confidence"] = {
        path: item.model_dump(mode="python", exclude_none=True) for path, item in metadata.confidence.items()
    }
    payload["rules"] = {
        path: item.model_dump(mode="python", exclude_none=True) for path, item in metadata.evidence.items()
    }
    payload["llm_recovery"] = metadata.recovery.model_dump(mode="python", exclude_none=True)
    payload["locked_fields"] = list(metadata.locking.locked_fields)
    payload["high_confidence_fields"] = list(metadata.locking.high_confidence_fields)
    return payload


__all__ = [
    "CanonicalProfileMetadata",
    "ConfidenceMeta",
    "ConfidenceTier",
    "DEFAULT_AI_TIER",
    "EvidenceMeta",
    "LockingMeta",
    "RULE_LOCK_TIER",
    "RecoveryMeta",
    "adapt_legacy_metadata",
    "export_metadata",
]
