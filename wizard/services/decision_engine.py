"""Decision backlog helpers used by follow-up generation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from models.decision_card import DecisionCard
from wizard.planner.plan_context import PlanContext, context_weight_for_field

_IMPACT_PRIORITY: dict[str, int] = {
    "Search": 0,
    "Selection": 1,
    "Candidate-Communication": 2,
}


def _normalize_card(raw: DecisionCard | Mapping[str, Any]) -> DecisionCard | None:
    """Coerce mapping payloads to ``DecisionCard`` instances."""

    if isinstance(raw, DecisionCard):
        return raw
    if not isinstance(raw, Mapping):
        return None
    try:
        return DecisionCard.model_validate(raw)
    except Exception:
        return None


def _decision_rank(card: DecisionCard, *, plan_context: PlanContext | None = None) -> tuple[int, int, int, str]:
    blocking_weight = 0 if card.blocking_exports else 1
    context_weight = context_weight_for_field(card.field_path, plan_context)
    impact_weight = _IMPACT_PRIORITY.get(card.impact_area, 3)
    return (blocking_weight, -context_weight, impact_weight, card.decision_id)


def build_decision_backlog(
    open_decisions: Sequence[DecisionCard | Mapping[str, Any]],
    *,
    max_items: int = 3,
    plan_context: PlanContext | None = None,
) -> list[DecisionCard]:
    """Return unresolved decisions prioritized by export impact area."""

    unresolved: list[DecisionCard] = []
    for raw in open_decisions:
        card = _normalize_card(raw)
        if card is None:
            continue
        if card.decision_state != "proposed":
            continue
        unresolved.append(card)

    prioritized = sorted(unresolved, key=lambda card: _decision_rank(card, plan_context=plan_context))
    if max_items <= 0:
        return []
    return prioritized[:max_items]


def decision_backlog_to_followups(
    cards: Sequence[DecisionCard],
    *,
    locale: str,
) -> list[dict[str, Any]]:
    """Render focused follow-up prompts from a decision backlog."""

    lang = "de" if locale.lower().startswith("de") else "en"
    followups: list[dict[str, Any]] = []
    for card in cards:
        options = list(card.suggested_resolution_options)
        if not options and card.proposed_value not in (None, ""):
            options = [str(card.proposed_value)]
        if not options:
            options = (
                ["Confirm proposal", "Provide alternative"]
                if lang == "en"
                else [
                    "Vorschlag bestätigen",
                    "Alternative angeben",
                ]
            )

        if lang == "de":
            question = f"Entscheidung offen: {card.title}. Wie soll final entschieden werden?"
        else:
            question = f"Open decision: {card.title}. What should we finalize?"

        followups.append(
            {
                "field": card.field_path,
                "question": question,
                "priority": "critical" if card.blocking_exports else "normal",
                "suggestions": options,
                "decision_id": card.decision_id,
                "category": card.category,
                "impact_area": card.impact_area,
                "blocking_exports": list(card.blocking_exports),
            }
        )
    return followups


__all__ = ["build_decision_backlog", "decision_backlog_to_followups"]
