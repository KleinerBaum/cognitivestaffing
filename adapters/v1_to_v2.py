"""Adapter utilities to map V1 need-analysis profiles into V2."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from models.decision_card import DecisionCard
from models.evidence import EvidenceItem, EvidenceSource
from models.need_analysis import NeedAnalysisProfile
from core.location_context import build_location_context
from models.need_analysis_v2 import NeedAnalysisV2


def _as_dict(v1_profile: NeedAnalysisProfile | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(v1_profile, NeedAnalysisProfile):
        return v1_profile.model_dump(mode="json")
    return dict(v1_profile)


def adapt_v1_to_v2(v1_profile: NeedAnalysisProfile | Mapping[str, Any]) -> NeedAnalysisV2:
    """Convert a V1 profile to V2 and mark undecided items as proposed."""

    raw = _as_dict(v1_profile)
    position = raw.get("position", {}) if isinstance(raw.get("position"), Mapping) else {}
    requirements = raw.get("requirements", {}) if isinstance(raw.get("requirements"), Mapping) else {}
    responsibilities = raw.get("responsibilities", {}) if isinstance(raw.get("responsibilities"), Mapping) else {}
    location = raw.get("location", {}) if isinstance(raw.get("location"), Mapping) else {}
    employment = raw.get("employment", {}) if isinstance(raw.get("employment"), Mapping) else {}
    process = raw.get("process", {}) if isinstance(raw.get("process"), Mapping) else {}
    compensation = raw.get("compensation", {}) if isinstance(raw.get("compensation"), Mapping) else {}
    meta = raw.get("meta", {}) if isinstance(raw.get("meta"), Mapping) else {}

    locale_bits = [location.get("primary_city") or "", location.get("country") or ""]
    locale_text = ", ".join(part for part in locale_bits if part)
    location_context = build_location_context(raw)

    evidence_items: list[EvidenceItem] = []
    open_decisions: list[DecisionCard] = []

    field_metadata_raw = meta.get("field_metadata") if isinstance(meta.get("field_metadata"), Mapping) else {}
    field_metadata: Mapping[str, Any] = cast(Mapping[str, Any], field_metadata_raw)
    for field_path, entry in field_metadata.items():
        if not isinstance(field_path, str) or not isinstance(entry, Mapping):
            continue
        source = str(entry.get("source") or "import").lower()
        source_value: EvidenceSource = cast(
            EvidenceSource,
            source if source in {"user", "llm", "heuristic", "import"} else "import",
        )
        confidence_raw = entry.get("confidence", 0.0)
        confidence = float(confidence_raw) if isinstance(confidence_raw, (int, float)) else 0.0
        excerpt = str(entry.get("evidence_snippet") or "")
        confirmed = bool(entry.get("confirmed", False))

        evidence_items.append(
            EvidenceItem(
                field_path=field_path,
                value=None,
                source=source_value,
                confidence=max(0.0, min(confidence, 1.0)),
                excerpt=excerpt,
            )
        )

        if not confirmed:
            open_decisions.append(
                DecisionCard(
                    decision_id=f"migration:{field_path}",
                    title=f"Klärung erforderlich: {field_path}",
                    field_path=field_path,
                    decision_state="proposed",
                    proposed_value=None,
                    rationale="Nicht entschieden (aus V1-Migration übernommen).",
                )
            )

    warnings: list[str] = []
    if open_decisions:
        warnings.append(f"{len(open_decisions)} Entscheidung(en) sind noch nicht bestätigt.")

    return NeedAnalysisV2.model_validate(
        {
            "intake": {
                "source_language": "",
                "raw_input": "",
                "target_locale": "",
            },
            "role": {
                "title": position.get("job_title") or "",
                "summary": position.get("role_summary") or "",
                "seniority": position.get("seniority_level") or "",
                "department": raw.get("department", {}).get("name", "")
                if isinstance(raw.get("department"), Mapping)
                else "",
                "team": raw.get("team", {}).get("name", "") if isinstance(raw.get("team"), Mapping) else "",
                "reports_to": position.get("reports_to") or "",
            },
            "work": {
                "responsibilities": responsibilities.get("items") or [],
                "location": locale_text,
                "city": location_context.city,
                "region": location_context.region,
                "country": location_context.country,
                "country_code": location_context.country_code,
                "work_policy": employment.get("work_policy") or "",
                "remote_policy": location_context.remote_policy,
                "travel_required": employment.get("travel_required"),
            },
            "requirements": {
                "hard_skills_required": requirements.get("hard_skills_required") or [],
                "hard_skills_optional": requirements.get("hard_skills_optional") or [],
                "soft_skills_required": requirements.get("soft_skills_required") or [],
                "soft_skills_optional": requirements.get("soft_skills_optional") or [],
                "languages_required": requirements.get("languages_required") or [],
                "certifications": requirements.get("certifications") or requirements.get("certificates") or [],
            },
            "constraints": {
                "visa_sponsorship": employment.get("visa_sponsorship"),
                "visa_policy": location_context.visa_policy,
                "relocation_policy": location_context.relocation_policy,
                "compensation_country_code": location_context.country_code,
                "compensation_currency": location_context.compensation_currency,
                "benefits_overlay": list(location_context.benefits_overlay),
                "salary_min": compensation.get("salary_min"),
                "salary_max": compensation.get("salary_max"),
                "currency": compensation.get("currency") or "",
                "timeline": process.get("recruitment_timeline") or "",
            },
            "selection": {
                "process_steps": process.get("hiring_process") or [],
                "stakeholders": [
                    stakeholder.get("name", "")
                    for stakeholder in process.get("stakeholders", [])
                    if isinstance(stakeholder, Mapping) and stakeholder.get("name")
                ],
            },
            "evidence": [item.model_dump(mode="json") for item in evidence_items],
            "open_decisions": [item.model_dump(mode="json") for item in open_decisions],
            "warnings": warnings,
        }
    )
