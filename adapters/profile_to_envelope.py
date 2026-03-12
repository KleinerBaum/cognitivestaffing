"""Adapter utilities to project NeedAnalysisProfile data into an envelope."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from models.evidence import EvidenceItem, EvidenceSource
from models.need_analysis import NeedAnalysisProfile
from models.need_analysis_envelope import EnvelopeFacts, EnvelopePlanItem, NeedAnalysisEnvelope


def _as_dict(profile: NeedAnalysisProfile | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(profile, NeedAnalysisProfile):
        return profile.model_dump(mode="json")
    return dict(profile)


def adapt_profile_to_envelope(profile: NeedAnalysisProfile | Mapping[str, Any]) -> NeedAnalysisEnvelope:
    """Convert a profile payload into the envelope representation."""

    payload = _as_dict(profile)
    meta = payload.get("meta") if isinstance(payload.get("meta"), Mapping) else {}

    evidence: list[EvidenceItem] = []
    field_metadata_raw = meta.get("field_metadata") if isinstance(meta, Mapping) else None
    field_metadata = field_metadata_raw if isinstance(field_metadata_raw, Mapping) else {}

    for field_path, entry in field_metadata.items():
        if not isinstance(field_path, str) or not isinstance(entry, Mapping):
            continue

        source_candidate = str(entry.get("source") or "import").lower()
        source_value: EvidenceSource = cast(
            EvidenceSource,
            source_candidate if source_candidate in {"user", "llm", "heuristic", "import"} else "import",
        )

        confidence_raw = entry.get("confidence", 1.0)
        confidence = float(confidence_raw) if isinstance(confidence_raw, (int, float)) else 1.0
        excerpt = str(entry.get("evidence_snippet") or "")

        evidence.append(
            EvidenceItem(
                field_path=field_path,
                value=None,
                source=source_value,
                confidence=max(0.0, min(confidence, 1.0)),
                excerpt=excerpt,
            )
        )

    facts = {key: value for key, value in payload.items() if key != "meta"}
    validated_facts = EnvelopeFacts.model_validate(facts).as_dict()

    return NeedAnalysisEnvelope(
        facts=validated_facts,
        evidence=evidence,
    )


def create_shadow_mode_snapshot(
    profile: NeedAnalysisProfile | Mapping[str, Any],
    *,
    trigger: str,
    step: str = "",
) -> NeedAnalysisEnvelope:
    """Build an envelope snapshot annotated for shadow-mode control-plane tracking."""

    envelope = adapt_profile_to_envelope(profile)
    envelope.plan.append(
        EnvelopePlanItem(
            action="snapshot",
            status="done",
            mode="shadow",
            trigger=trigger,
            step=step,
        )
    )
    return envelope
