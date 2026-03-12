"""Heuristic risk detection for decision-first planning."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from models.decision_card import DecisionCard, DecisionCategory, ImpactArea
from wizard.planner.plan_context import PlanContext


@dataclass(frozen=True)
class _RiskRule:
    code: str
    title: str
    field_path: str
    category: DecisionCategory
    impact_area: ImpactArea
    keywords: tuple[str, ...]


_RISK_RULES: tuple[_RiskRule, ...] = (
    _RiskRule(
        code="stakeholder_complexity",
        title="Stakeholder alignment complexity",
        field_path="selection.stakeholders",
        category="selection",
        impact_area="Selection",
        keywords=("stakeholder", "matrix", "cross-functional", "schnittstelle", "betriebsrat"),
    ),
    _RiskRule(
        code="conflict_heavy_interface",
        title="Conflict exposure in role interfaces",
        field_path="selection.process_steps",
        category="selection",
        impact_area="Selection",
        keywords=("conflict", "escalation", "mediation", "konflikt", "eskalation"),
    ),
    _RiskRule(
        code="political_sensitivity",
        title="Political sensitivity in hiring context",
        field_path="role.summary",
        category="selection",
        impact_area="Selection",
        keywords=("politic", "confidential", "board", "reorg", "transformation", "politisch"),
    ),
    _RiskRule(
        code="communication_constraints",
        title="Communication constraints to clarify early",
        field_path="requirements.languages_required",
        category="candidate_communication",
        impact_area="Candidate-Communication",
        keywords=("timezone", "async", "distributed", "language", "mehrsprach", "bilingual"),
    ),
    _RiskRule(
        code="pressure_patterns",
        title="Pressure pattern and timeline realism",
        field_path="constraints.timeline",
        category="search",
        impact_area="Search",
        keywords=("urgent", "asap", "immediate", "dringend", "schnellstmöglich", "timeline pressure"),
    ),
    _RiskRule(
        code="leadership_style_compatibility",
        title="Leadership style compatibility",
        field_path="requirements.soft_skills_required",
        category="selection",
        impact_area="Selection",
        keywords=("leadership", "autonomy", "hands-on", "micromanag", "führungsstil"),
    ),
)


def detect_risk_decision_cards(
    profile: Mapping[str, Any],
    *,
    evidence: Sequence[Mapping[str, Any]] | None = None,
    plan_context: PlanContext | None = None,
) -> list[DecisionCard]:
    """Detect collaboration/work-environment risks as inferred decision cards."""

    profile_text = _build_profile_text(profile)
    evidence_text = _build_evidence_text(
        evidence if evidence is not None else _coerce_evidence(profile.get("evidence"))
    )
    context_text = _build_context_text(plan_context)

    cards: list[DecisionCard] = []
    for rule in _RISK_RULES:
        confidence, rationale = _evaluate_rule(rule, profile, profile_text, evidence_text, context_text)
        if confidence <= 0.0:
            continue
        confidence_label = "high" if confidence >= 0.75 else "medium" if confidence >= 0.55 else "low"
        options = _resolution_options(confidence_label)
        cards.append(
            DecisionCard(
                decision_id=f"risk-{rule.code}",
                title=rule.title,
                field_path=rule.field_path,
                decision_state="proposed",
                proposed_value=None,
                rationale=rationale,
                category=rule.category,
                impact_area=rule.impact_area,
                blocking_exports=[],
                suggested_resolution_options=options,
            )
        )

    cards.sort(key=lambda card: card.decision_id)
    return cards


def _evaluate_rule(
    rule: _RiskRule,
    profile: Mapping[str, Any],
    profile_text: str,
    evidence_text: str,
    context_text: str,
) -> tuple[float, str]:
    hits_profile = sum(1 for keyword in rule.keywords if keyword in profile_text)
    hits_evidence = sum(1 for keyword in rule.keywords if keyword in evidence_text)
    hits_context = sum(1 for keyword in rule.keywords if keyword in context_text)

    confidence = 0.0
    reasons: list[str] = []

    if rule.code == "stakeholder_complexity":
        stakeholders = _get_path(profile, "selection.stakeholders")
        if isinstance(stakeholders, Sequence) and not isinstance(stakeholders, (str, bytes)):
            size = len([item for item in stakeholders if str(item).strip()])
            if size >= 4:
                confidence = max(confidence, 0.85)
                reasons.append(f"{size} stakeholders listed")
            elif size >= 3:
                confidence = max(confidence, 0.65)
                reasons.append(f"{size} stakeholders listed")

    if rule.code == "communication_constraints":
        languages = _get_path(profile, "requirements.languages_required")
        if isinstance(languages, Sequence) and not isinstance(languages, (str, bytes)):
            size = len([item for item in languages if str(item).strip()])
            if size >= 2:
                confidence = max(confidence, 0.6)
                reasons.append("multiple required languages")

    if rule.code == "pressure_patterns":
        urgency = str(_get_path(profile, "constraints.timeline") or "").strip().lower()
        if urgency and any(token in urgency for token in ("asap", "urgent", "immediate", "dringend", "schnell")):
            confidence = max(confidence, 0.75)
            reasons.append("timeline wording indicates pressure")

    if hits_profile > 0:
        confidence = max(confidence, min(0.8, 0.45 + 0.15 * hits_profile))
        reasons.append("profile cue(s) matched")
    if hits_evidence > 0:
        confidence = max(confidence, min(0.85, 0.5 + 0.15 * hits_evidence))
        reasons.append("evidence cue(s) matched")
    if hits_context > 0:
        confidence = max(confidence, min(0.65, 0.4 + 0.1 * hits_context))
        reasons.append("planning context cue(s) matched")

    if confidence < 0.45:
        return 0.0, ""

    if confidence < 0.6:
        prefix = "Inferred signal (low confidence)."
    else:
        prefix = "Potential signal."
    rationale = prefix
    if reasons:
        rationale += " " + "; ".join(dict.fromkeys(reasons)) + "."
    return confidence, rationale


def _resolution_options(confidence_label: str) -> list[str]:
    if confidence_label == "low":
        return [
            "Clarify whether this risk is relevant",
            "Not relevant in this hiring context",
            "Need more context before deciding",
        ]
    return [
        "Confirm this risk should guide follow-up",
        "Partially relevant; scope it",
        "Not relevant in this hiring context",
    ]


def _build_profile_text(profile: Mapping[str, Any]) -> str:
    selected_values = [
        _get_path(profile, "role.summary"),
        _get_path(profile, "position.role_summary"),
        _get_path(profile, "work.work_policy"),
        _get_path(profile, "constraints.timeline"),
        _get_path(profile, "process.recruitment_timeline"),
        _get_path(profile, "warnings"),
    ]
    return " ".join(_flatten_to_strings(selected_values)).lower()


def _build_evidence_text(evidence: Sequence[Mapping[str, Any]]) -> str:
    parts: list[str] = []
    for item in evidence:
        excerpt = str(item.get("excerpt") or "").strip()
        field_path = str(item.get("field_path") or "").strip()
        if excerpt:
            parts.append(excerpt)
        if field_path:
            parts.append(field_path)
    return " ".join(parts).lower()


def _build_context_text(plan_context: PlanContext | None) -> str:
    if plan_context is None:
        return ""
    values = [*plan_context.risk_signals, plan_context.hiring_urgency or ""]
    return " ".join(_flatten_to_strings(values)).lower()


def _coerce_evidence(raw: Any) -> list[Mapping[str, Any]]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    items: list[Mapping[str, Any]] = []
    for item in raw:
        if isinstance(item, Mapping):
            items.append(item)
    return items


def _get_path(data: Mapping[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _flatten_to_strings(values: Sequence[Any]) -> list[str]:
    items: list[str] = []
    for value in values:
        if isinstance(value, (list, tuple, set)):
            items.extend(_flatten_to_strings(list(value)))
            continue
        text = str(value or "").strip()
        if text:
            items.append(text)
    return items


__all__ = ["detect_risk_decision_cards"]
